#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <fstream>
#include <functional>
#include <iomanip>
#include <mutex>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>

#include "geometry_msgs/msg/twist.hpp"
#include "geometry_msgs/msg/twist_stamped.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"
#include "yhs_can_control/odom_distance_test_logic.hpp"
#include "yhs_can_interfaces/msg/chassis_info_fb.hpp"

// 这个节点是实车测试工具，不是新的底层距离控制协议：
// 它发低速 /cmd_vel，用 /odom 判断何时停车，并把结果打印或写入 CSV。

namespace
{

template<typename T>
T declare_and_get(rclcpp::Node & node, const std::string & name, const T & default_value)
{
  node.declare_parameter<T>(name, default_value);
  return node.get_parameter(name).get_value<T>();
}

std::string now_for_csv()
{
  const auto now = std::chrono::system_clock::now();
  const auto time_t_now = std::chrono::system_clock::to_time_t(now);
  std::tm tm_now{};
#ifdef _WIN32
  localtime_s(&tm_now, &time_t_now);
#else
  localtime_r(&time_t_now, &tm_now);
#endif
  std::ostringstream stream;
  stream << std::put_time(&tm_now, "%Y-%m-%dT%H:%M:%S");
  return stream.str();
}

bool file_is_empty(const std::string & path)
{
  // CSV 第一次写入时需要表头；已有内容时直接追加一行结果。
  std::ifstream input(path, std::ios::binary);
  return !input.good() || input.peek() == std::ifstream::traits_type::eof();
}

}  // namespace

class OdomDistanceTestNode : public rclcpp::Node
{
public:
  OdomDistanceTestNode()
  : Node("odom_distance_test_node")
  {
    config_.armed = declare_and_get<bool>(*this, "armed", false);
    config_.target_distance_m = declare_and_get<double>(*this, "target_distance_m", 1.0);
    config_.target_speed_mps = declare_and_get<double>(*this, "target_speed_mps", 0.5);
    cmd_vel_topic_ = declare_and_get<std::string>(*this, "cmd_vel_topic", "cmd_vel");
    odom_topic_ = declare_and_get<std::string>(*this, "odom_topic", "odom");
    chassis_info_topic_ =
      declare_and_get<std::string>(*this, "chassis_info_topic", "chassis_info_fb");
    command_rate_hz_ = declare_and_get<double>(*this, "command_rate_hz", 20.0);
    stop_hold_sec_ = declare_and_get<double>(*this, "stop_hold_sec", 1.0);
    config_.max_runtime_sec = declare_and_get<double>(*this, "max_runtime_sec", 60.0);
    config_.distance_tolerance_m =
      declare_and_get<double>(*this, "distance_tolerance_m", 0.01);
    use_stamped_cmd_vel_ = declare_and_get<bool>(*this, "use_stamped_cmd_vel", false);
    log_csv_path_ = declare_and_get<std::string>(*this, "log_csv_path", "");

    validate_parameters();
    prepare_csv_if_requested();

    // 与 cmd_vel_to_ctrl_cmd_node 保持一致：默认 Twist，可选 TwistStamped。
    if (use_stamped_cmd_vel_) {
      stamped_cmd_pub_ =
        create_publisher<geometry_msgs::msg::TwistStamped>(cmd_vel_topic_, rclcpp::QoS(10));
    } else {
      twist_cmd_pub_ =
        create_publisher<geometry_msgs::msg::Twist>(cmd_vel_topic_, rclcpp::QoS(10));
    }

    odom_sub_ = create_subscription<nav_msgs::msg::Odometry>(
      odom_topic_, rclcpp::QoS(10),
      [this](const nav_msgs::msg::Odometry::SharedPtr msg) {
        // 只取平面 x/y；直线距离测试不依赖高度和姿态。
        std::lock_guard<std::mutex> lock(data_mutex_);
        latest_odom_ = yhs::mk_mini::odom_test::OdomSample{
          msg->pose.pose.position.x,
          msg->pose.pose.position.y};
      });

    chassis_info_sub_ = create_subscription<yhs_can_interfaces::msg::ChassisInfoFb>(
      chassis_info_topic_, rclcpp::QoS(10),
      [this](const yhs_can_interfaces::msg::ChassisInfoFb::SharedPtr msg) {
        // 底盘累计里程只用于记录和对比，不用它控制停车。
        std::lock_guard<std::mutex> lock(data_mutex_);
        latest_chassis_mileage_m_ = msg->odo_fb.odo_fb_accumulative_mileage;
      });

    const auto period = std::chrono::duration<double>(1.0 / command_rate_hz_);
    timer_ = create_wall_timer(
      std::chrono::duration_cast<std::chrono::nanoseconds>(period),
      std::bind(&OdomDistanceTestNode::on_timer, this));

    RCLCPP_INFO(
      get_logger(),
      "odom distance test ready: armed=%s, target=%.3f m, speed=%.3f m/s, topic=%s",
      config_.armed ? "true" : "false",
      config_.target_distance_m,
      config_.target_speed_mps,
      cmd_vel_topic_.c_str());
  }

private:
  void validate_parameters() const
  {
    // 参数错误时直接拒绝启动，避免实车测试中出现不可预测运动。
    if (config_.target_distance_m <= 0.0) {
      throw std::runtime_error("target_distance_m must be greater than 0");
    }
    if (config_.target_speed_mps <= 0.0) {
      throw std::runtime_error("target_speed_mps must be greater than 0");
    }
    if (command_rate_hz_ <= 0.0) {
      throw std::runtime_error("command_rate_hz must be greater than 0");
    }
    if (stop_hold_sec_ <= 0.0) {
      throw std::runtime_error("stop_hold_sec must be greater than 0");
    }
    if (config_.max_runtime_sec <= 0.0) {
      throw std::runtime_error("max_runtime_sec must be greater than 0");
    }
    if (config_.distance_tolerance_m < 0.0) {
      throw std::runtime_error("distance_tolerance_m must be non-negative");
    }
  }

  void prepare_csv_if_requested() const
  {
    if (log_csv_path_.empty()) {
      return;
    }

    const bool needs_header = file_is_empty(log_csv_path_);
    std::ofstream output(log_csv_path_, std::ios::app);
    if (!output.is_open()) {
      throw std::runtime_error("failed to open log_csv_path: " + log_csv_path_);
    }
    if (needs_header) {
      output
        << "timestamp,target_distance_m,target_speed_mps,odom_start_x,odom_start_y,"
        << "odom_end_x,odom_end_y,odom_distance_m,chassis_mileage_delta_m,"
        << "runtime_sec,end_reason\n";
    }
  }

  void on_timer()
  {
    // 定时器是唯一发布 /cmd_vel 的地方，便于保证停车和保活逻辑一致。
    const double now_sec = now().seconds();

    std::optional<yhs::mk_mini::odom_test::OdomSample> odom;
    std::optional<double> chassis_mileage;
    {
      std::lock_guard<std::mutex> lock(data_mutex_);
      odom = latest_odom_;
      chassis_mileage = latest_chassis_mileage_m_;
    }

    const auto result = controller_.update(config_, odom, now_sec);

    if (result.started_now) {
      // 起点和底盘累计里程的初值必须在同一个启动周期记录，方便后续计算增量。
      odom_start_ = odom;
      chassis_start_mileage_m_ = chassis_mileage;
      RCLCPP_INFO(
        get_logger(),
        "odom distance test started: target=%.3f m, speed=%.3f m/s",
        config_.target_distance_m,
        config_.target_speed_mps);
    }

    publish_velocity(result.command_velocity_mps);

    if (result.reason == yhs::mk_mini::odom_test::EndReason::kWaitingForOdom) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 2000,
        "waiting for odom before publishing motion command");
    } else if (result.reason == yhs::mk_mini::odom_test::EndReason::kNotArmed) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 5000,
        "armed=false; set -p armed:=true to run the distance test");
    }

    if (result.terminal && !reported_) {
      // 只报告一次结果；之后继续保持 0 速一段时间再退出。
      reported_ = true;
      finish_wall_time_sec_ = now_sec;
      odom_end_ = odom;
      chassis_end_mileage_m_ = chassis_mileage;
      report_result(result);
      append_csv_result(result);
    }

    if (reported_ && (now_sec - finish_wall_time_sec_) >= stop_hold_sec_) {
      publish_velocity(0.0);
      RCLCPP_INFO(get_logger(), "stop hold complete; shutting down odom distance test node");
      rclcpp::shutdown();
    }
  }

  void publish_velocity(const double velocity_mps)
  {
    if (use_stamped_cmd_vel_) {
      geometry_msgs::msg::TwistStamped msg;
      msg.header.stamp = now();
      msg.header.frame_id = "";
      msg.twist.linear.x = velocity_mps;
      msg.twist.angular.z = 0.0;
      stamped_cmd_pub_->publish(msg);
      return;
    }

    geometry_msgs::msg::Twist msg;
    msg.linear.x = velocity_mps;
    msg.angular.z = 0.0;
    twist_cmd_pub_->publish(msg);
  }

  std::optional<double> chassis_mileage_delta() const
  {
    if (!chassis_start_mileage_m_.has_value() || !chassis_end_mileage_m_.has_value()) {
      return std::nullopt;
    }
    return chassis_end_mileage_m_.value() - chassis_start_mileage_m_.value();
  }

  void report_result(const yhs::mk_mini::odom_test::UpdateResult & result) const
  {
    const auto chassis_delta = chassis_mileage_delta();
    const std::string chassis_delta_text =
      chassis_delta.has_value() ? format_double(chassis_delta.value()) : "n/a";
    RCLCPP_INFO(
      get_logger(),
      "odom distance test finished: reason=%s, target=%.3f m, odom=%.3f m, "
      "chassis_delta=%s, runtime=%.3f s",
      yhs::mk_mini::odom_test::to_string(result.reason),
      config_.target_distance_m,
      result.odom_distance_m,
      chassis_delta_text.c_str(),
      result.runtime_sec);
  }

  std::string format_double(const double value) const
  {
    std::ostringstream stream;
    stream << std::fixed << std::setprecision(6) << value;
    return stream.str();
  }

  void append_csv_result(const yhs::mk_mini::odom_test::UpdateResult & result) const
  {
    if (log_csv_path_.empty()) {
      return;
    }

    std::ofstream output(log_csv_path_, std::ios::app);
    if (!output.is_open()) {
      RCLCPP_ERROR(get_logger(), "failed to append CSV log: %s", log_csv_path_.c_str());
      return;
    }

    const auto chassis_delta = chassis_mileage_delta();
    output
      << now_for_csv() << ','
      << config_.target_distance_m << ','
      << config_.target_speed_mps << ','
      << (odom_start_.has_value() ? odom_start_->x : 0.0) << ','
      << (odom_start_.has_value() ? odom_start_->y : 0.0) << ','
      << (odom_end_.has_value() ? odom_end_->x : 0.0) << ','
      << (odom_end_.has_value() ? odom_end_->y : 0.0) << ','
      << result.odom_distance_m << ','
      << (chassis_delta.has_value() ? format_double(chassis_delta.value()) : "") << ','
      << result.runtime_sec << ','
      << yhs::mk_mini::odom_test::to_string(result.reason) << '\n';
  }

  yhs::mk_mini::odom_test::Config config_;
  yhs::mk_mini::odom_test::DistanceTestController controller_;

  std::string cmd_vel_topic_;
  std::string odom_topic_;
  std::string chassis_info_topic_;
  double command_rate_hz_{20.0};
  double stop_hold_sec_{1.0};
  bool use_stamped_cmd_vel_{false};
  std::string log_csv_path_;

  std::mutex data_mutex_;
  std::optional<yhs::mk_mini::odom_test::OdomSample> latest_odom_;
  std::optional<double> latest_chassis_mileage_m_;

  bool reported_{false};
  double finish_wall_time_sec_{0.0};
  std::optional<yhs::mk_mini::odom_test::OdomSample> odom_start_;
  std::optional<yhs::mk_mini::odom_test::OdomSample> odom_end_;
  std::optional<double> chassis_start_mileage_m_;
  std::optional<double> chassis_end_mileage_m_;

  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr twist_cmd_pub_;
  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr stamped_cmd_pub_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
  rclcpp::Subscription<yhs_can_interfaces::msg::ChassisInfoFb>::SharedPtr chassis_info_sub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  try {
    rclcpp::spin(std::make_shared<OdomDistanceTestNode>());
  } catch (const std::exception & ex) {
    RCLCPP_FATAL(rclcpp::get_logger("odom_distance_test_node"), "startup failed: %s", ex.what());
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::shutdown();
  return 0;
}
