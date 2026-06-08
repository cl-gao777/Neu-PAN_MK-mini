#include <algorithm>
#include <cmath>
#include <mutex>
#include <string>

#include "geometry_msgs/msg/twist.hpp"
#include "geometry_msgs/msg/twist_stamped.hpp"
#include "rclcpp/rclcpp.hpp"
#include "yhs_can_interfaces/msg/ctrl_cmd.hpp"

// 这个节点是 Nav2 和 MK-mini 底盘之间的适配层：
// Nav2 发布 /cmd_vel，本节点转换成厂家底盘使用的 /ctrl_cmd。

namespace
{

constexpr double kRadToDeg = 180.0 / 3.14159265358979323846;
constexpr double kMinTurningVelocity = 1e-3;

template<typename T>
T declare_and_get(rclcpp::Node & node, const std::string & name, const T & default_value)
{
  node.declare_parameter<T>(name, default_value);
  return node.get_parameter(name).get_value<T>();
}

double clamp_abs(const double value, const double limit)
{
  // 对称限幅：既限制正向速度/转角，也限制反向速度/转角。
  const double abs_limit = std::abs(limit);
  return std::clamp(value, -abs_limit, abs_limit);
}

}  // namespace

class CmdVelToCtrlCmdNode : public rclcpp::Node
{
public:
  CmdVelToCtrlCmdNode()
  : Node("cmd_vel_to_ctrl_cmd_node")
  {
    // 默认兼容 ROS 2 Jazzy/Nav2 的 Twist；如后续栈使用 TwistStamped，可通过参数切换。
    input_topic_ = declare_and_get<std::string>(*this, "input_topic", "cmd_vel");
    output_topic_ = declare_and_get<std::string>(*this, "output_topic", "ctrl_cmd");
    wheel_base_ = declare_and_get<double>(*this, "wheel_base", 0.6);
    publish_rate_hz_ = declare_and_get<double>(*this, "ctrl_cmd_publish_rate_hz", 50.0);
    timeout_sec_ = declare_and_get<double>(*this, "cmd_vel_timeout_sec", 0.3);
    max_velocity_mps_ = declare_and_get<double>(*this, "max_velocity_mps", 0.3);
    max_steering_deg_ = declare_and_get<double>(*this, "max_steering_deg", 25.0);
    allow_reverse_ = declare_and_get<bool>(*this, "allow_reverse", false);
    use_stamped_cmd_vel_ = declare_and_get<bool>(*this, "use_stamped_cmd_vel", false);
    forward_gear_ = static_cast<std::uint8_t>(declare_and_get<int>(*this, "forward_gear", 1));
    reverse_gear_ = static_cast<std::uint8_t>(declare_and_get<int>(*this, "reverse_gear", 2));

    if (wheel_base_ <= 0.0) {
      throw std::runtime_error("wheel_base 必须大于 0");
    }
    if (publish_rate_hz_ <= 0.0) {
      throw std::runtime_error("ctrl_cmd_publish_rate_hz 必须大于 0");
    }
    if (timeout_sec_ <= 0.0) {
      throw std::runtime_error("cmd_vel_timeout_sec 必须大于 0");
    }

    ctrl_cmd_pub_ =
      create_publisher<yhs_can_interfaces::msg::CtrlCmd>(output_topic_, rclcpp::SensorDataQoS());

    if (use_stamped_cmd_vel_) {
      stamped_sub_ = create_subscription<geometry_msgs::msg::TwistStamped>(
        input_topic_, rclcpp::SensorDataQoS(),
        [this](const geometry_msgs::msg::TwistStamped::SharedPtr msg) {
          update_command(msg->twist);
        });
    } else {
      twist_sub_ = create_subscription<geometry_msgs::msg::Twist>(
        input_topic_, rclcpp::SensorDataQoS(),
        [this](const geometry_msgs::msg::Twist::SharedPtr msg) {
          update_command(*msg);
        });
    }

    const auto period = std::chrono::duration<double>(1.0 / publish_rate_hz_);
    publish_timer_ = create_wall_timer(
      std::chrono::duration_cast<std::chrono::nanoseconds>(period),
      std::bind(&CmdVelToCtrlCmdNode::publish_command, this));
  }

private:
  void update_command(const geometry_msgs::msg::Twist & twist)
  {
    // 这里只更新“期望指令”；真正发布由定时器完成，保证底盘有固定频率保活指令。
    std::lock_guard<std::mutex> lock(command_mutex_);
    last_cmd_time_ = now();
    have_cmd_ = true;

    double linear_x = clamp_abs(twist.linear.x, max_velocity_mps_);
    const double angular_z = twist.angular.z;

    if (linear_x < 0.0 && !allow_reverse_) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 2000,
        "倒车 cmd_vel 已禁用，正在发布停车指令。");
      desired_cmd_ = make_stop_command();
      return;
    }

    if (std::abs(linear_x) < kMinTurningVelocity) {
      if (std::abs(angular_z) > 1e-6) {
        RCLCPP_WARN_THROTTLE(
          get_logger(), *get_clock(), 2000,
          "忽略线速度接近 0 的角速度 cmd_vel；MK-mini 不能原地旋转。");
      }
      desired_cmd_ = make_stop_command();
      return;
    }

    // Ackermann 转换：给定线速度 v 和角速度 w，转角 = atan(wheel_base * w / v)。
    const double steering_rad = std::atan(wheel_base_ * angular_z / linear_x);
    const double steering_deg = clamp_abs(steering_rad * kRadToDeg, max_steering_deg_);

    yhs_can_interfaces::msg::CtrlCmd cmd;
    cmd.ctrl_cmd_gear = linear_x < 0.0 ? reverse_gear_ : forward_gear_;
    cmd.ctrl_cmd_velocity = static_cast<float>(std::abs(linear_x));
    cmd.ctrl_cmd_steering = static_cast<float>(steering_deg);
    desired_cmd_ = cmd;
  }

  yhs_can_interfaces::msg::CtrlCmd make_stop_command() const
  {
    // 停车时仍使用前进挡位和 0 速，避免发送负速度或未知挡位。
    yhs_can_interfaces::msg::CtrlCmd cmd;
    cmd.ctrl_cmd_gear = forward_gear_;
    cmd.ctrl_cmd_velocity = 0.0f;
    cmd.ctrl_cmd_steering = 0.0f;
    return cmd;
  }

  void publish_command()
  {
    // 超过 timeout_sec 没收到新 /cmd_vel 时，持续发布 0 速，防止车辆沿用旧指令。
    yhs_can_interfaces::msg::CtrlCmd cmd;
    {
      std::lock_guard<std::mutex> lock(command_mutex_);
      if (!have_cmd_ || (now() - last_cmd_time_).seconds() > timeout_sec_) {
        cmd = make_stop_command();
      } else {
        cmd = desired_cmd_;
      }
    }
    ctrl_cmd_pub_->publish(cmd);
  }

  std::string input_topic_;
  std::string output_topic_;
  double wheel_base_{0.6};
  double publish_rate_hz_{50.0};
  double timeout_sec_{0.3};
  double max_velocity_mps_{0.3};
  double max_steering_deg_{25.0};
  bool allow_reverse_{false};
  bool use_stamped_cmd_vel_{false};
  std::uint8_t forward_gear_{1};
  std::uint8_t reverse_gear_{2};

  std::mutex command_mutex_;
  bool have_cmd_{false};
  rclcpp::Time last_cmd_time_{0, 0, RCL_ROS_TIME};
  yhs_can_interfaces::msg::CtrlCmd desired_cmd_;

  rclcpp::Publisher<yhs_can_interfaces::msg::CtrlCmd>::SharedPtr ctrl_cmd_pub_;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr twist_sub_;
  rclcpp::Subscription<geometry_msgs::msg::TwistStamped>::SharedPtr stamped_sub_;
  rclcpp::TimerBase::SharedPtr publish_timer_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  try {
    rclcpp::spin(std::make_shared<CmdVelToCtrlCmdNode>());
  } catch (const std::exception & ex) {
    RCLCPP_FATAL(rclcpp::get_logger("cmd_vel_to_ctrl_cmd_node"), "启动失败：%s", ex.what());
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::shutdown();
  return 0;
}
