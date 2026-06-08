#ifndef YHS_CAN_CONTROL_YHS_CAN_CONTROL_NODE_HPP_
#define YHS_CAN_CONTROL_YHS_CAN_CONTROL_NODE_HPP_

#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>

#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <vector>

#include "geometry_msgs/msg/pose_with_covariance.hpp"
#include "geometry_msgs/msg/transform_stamped.hpp"
#include "geometry_msgs/msg/twist_with_covariance.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"
#include "tf2/LinearMath/Quaternion.h"
#include "tf2_ros/transform_broadcaster.h"
#include "yhs_can_control/mk_mini_protocol.hpp"
#include "yhs_can_interfaces/msg/chassis_info_fb.hpp"
#include "yhs_can_interfaces/msg/ctrl_cmd.hpp"
#include "yhs_can_interfaces/msg/io_cmd.hpp"

namespace yhs
{

// 底盘驱动核心类：
// 订阅 ROS 控制指令并写入 CAN，同时接收底盘反馈并发布 /chassis_info_fb、/odom 和 TF。
class CanControl
{
public:
  explicit CanControl(rclcpp::Node::SharedPtr node);
  ~CanControl();

  bool run();
  void stop();

private:
  rclcpp::Node::SharedPtr node_;

  // SocketCAN 状态；can_socket_ 为 -1 表示当前没有打开 CAN 设备。
  std::string if_name_;
  int can_socket_{-1};
  double wheel_base_{0.6};
  bool publish_odom_tf_{true};
  std::string odom_frame_id_{"odom"};
  std::string base_frame_id_{"base_link"};

  std::atomic_bool running_{false};
  std::thread thread_;
  std::mutex socket_mutex_;

  // 厂家超声波原始顺序可通过参数映射到消息里的前后左右方位。
  std::vector<int64_t> ultrasonic_number_;
  std::array<std::uint16_t, 8> ultrasonic_data_{};
  yhs_can_interfaces::msg::ChassisInfoFb chassis_info_msg_;

  std::uint8_t ctrl_alive_count_{0};
  std::uint8_t io_alive_count_{0};

  // 发布 /odom 使用的累计位姿。
  double x_{0.0};
  double y_{0.0};
  double theta_{0.0};
  rclcpp::Time last_odom_time_;
  bool have_odom_time_{false};
  bool have_odo_feedback_{false};
  double last_odo_mileage_{0.0};
  double last_odo_heading_{0.0};

  rclcpp::Subscription<yhs_can_interfaces::msg::IoCmd>::SharedPtr io_cmd_subscriber_;
  rclcpp::Subscription<yhs_can_interfaces::msg::CtrlCmd>::SharedPtr ctrl_cmd_subscriber_;

  rclcpp::Publisher<yhs_can_interfaces::msg::ChassisInfoFb>::SharedPtr chassis_info_fb_publisher_;
  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odom_pub_;
  std::unique_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_;

  void io_cmd_callback(const yhs_can_interfaces::msg::IoCmd::SharedPtr io_cmd_msg);
  void ctrl_cmd_callback(const yhs_can_interfaces::msg::CtrlCmd::SharedPtr ctrl_cmd_msg);

  bool wait_for_can_frame();
  void can_data_recv_callback();
  bool write_frame(std::uint32_t can_id, const mk_mini::FrameData & data);

  bool validate_ultrasonic_mapping() const;
  void publish_chassis_info();
  // 没有底盘 ODO 反馈时，临时使用控制反馈速度积分；收到 ODO 后优先使用底盘 ODO。
  void publish_integrated_odom(double velocity_mps, double steering_rad);
  void publish_odo_feedback_odom(const mk_mini::OdoFeedback & feedback);
  void publish_odom_message(
    const rclcpp::Time & stamp, double linear_velocity, double angular_velocity);
};

}  // namespace yhs

#endif  // YHS_CAN_CONTROL_YHS_CAN_CONTROL_NODE_HPP_
