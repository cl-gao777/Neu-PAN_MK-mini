#include "yhs_can_control/yhs_can_control_node.hpp"

#include <cerrno>
#include <chrono>
#include <cstring>
#include <stdexcept>

#include "yhs_can_control/socketcan_helpers.hpp"

// 这个文件实现 MK-mini 底盘 ROS 2 节点：
// 1. 打开 Linux SocketCAN；
// 2. 把 /ctrl_cmd、/io_cmd 编码成 CAN 指令；
// 3. 把底盘反馈解析后发布到 /chassis_info_fb、/veh_diag_fb、/odom 和 TF。

namespace yhs
{
namespace
{

constexpr double kDegToRad = 3.14159265358979323846 / 180.0;

double steady_now_sec()
{
  return std::chrono::duration<double>(
    std::chrono::steady_clock::now().time_since_epoch()).count();
}

template<typename T>
T declare_and_get(
  const rclcpp::Node::SharedPtr & node, const std::string & name, const T & default_value)
{
  node->declare_parameter<T>(name, default_value);
  return node->get_parameter(name).get_value<T>();
}

mk_mini::FrameData frame_data_from_can(const can_frame & frame)
{
  mk_mini::FrameData data{};
  std::memcpy(data.data(), frame.data, data.size());
  return data;
}

}  // namespace

CanControl::CanControl(rclcpp::Node::SharedPtr node)
: node_(std::move(node))
{
  // 参数从 cfg.yaml 读取；没有配置时使用保守默认值。
  if_name_ = declare_and_get<std::string>(node_, "can_name", "can4");
  wheel_base_ = declare_and_get<double>(node_, "wheel_base", 0.6);
  publish_odom_tf_ = declare_and_get<bool>(node_, "publish_odom_tf", true);
  odom_frame_id_ = declare_and_get<std::string>(node_, "odom_frame_id", "odom");
  base_frame_id_ = declare_and_get<std::string>(node_, "base_frame_id", "base_link");
  ultrasonic_number_ = declare_and_get<std::vector<int64_t>>(
    node_, "ultrasonic_number", std::vector<int64_t>{0, 1, 2, 3, 4, 5, 6, 7});

  ControlCommandGateConfig control_config;
  control_config.max_velocity_mps =
    declare_and_get<double>(node_, "max_velocity_mps", control_config.max_velocity_mps);
  control_config.max_steering_deg =
    declare_and_get<double>(node_, "max_steering_deg", control_config.max_steering_deg);
  control_config.command_timeout_sec =
    declare_and_get<double>(node_, "command_timeout_sec", control_config.command_timeout_sec);
  control_config.send_rate_hz =
    declare_and_get<double>(node_, "send_rate_hz", control_config.send_rate_hz);
  control_config.allow_reverse =
    declare_and_get<bool>(node_, "allow_reverse", control_config.allow_reverse);
  control_config.forward_gear = static_cast<std::uint8_t>(
    declare_and_get<int>(node_, "forward_gear", control_config.forward_gear));
  control_config.reverse_gear = static_cast<std::uint8_t>(
    declare_and_get<int>(node_, "reverse_gear", control_config.reverse_gear));

  if (wheel_base_ <= 0.0) {
    throw std::runtime_error("wheel_base 必须大于 0");
  }
  if (!validate_ultrasonic_mapping()) {
    throw std::runtime_error("ultrasonic_number 必须包含 8 个索引，且每个索引都在 [0, 7] 范围内");
  }
  if (!std::isfinite(control_config.max_velocity_mps) ||
    control_config.max_velocity_mps <= 0.0)
  {
    throw std::runtime_error("max_velocity_mps 必须是大于 0 的有限值");
  }
  if (!std::isfinite(control_config.max_steering_deg) ||
    control_config.max_steering_deg <= 0.0)
  {
    throw std::runtime_error("max_steering_deg 必须是大于 0 的有限值");
  }
  if (!std::isfinite(control_config.command_timeout_sec) ||
    control_config.command_timeout_sec <= 0.0)
  {
    throw std::runtime_error("command_timeout_sec 必须是大于 0 的有限值");
  }
  if (!std::isfinite(control_config.send_rate_hz) || control_config.send_rate_hz <= 0.0) {
    throw std::runtime_error("send_rate_hz 必须是大于 0 的有限值");
  }
  if (control_config.forward_gear != 4 || control_config.reverse_gear != 2) {
    throw std::runtime_error("MK-mini 官方前进/倒车挡位必须分别为 D=4 和 R=2");
  }
  control_command_gate_ = ControlCommandGate(control_config);

  // 原厂接口：上层可以直接发 /io_cmd 和 /ctrl_cmd；Nav2 的 /cmd_vel 会先由适配节点转成 /ctrl_cmd。
  io_cmd_subscriber_ = node_->create_subscription<yhs_can_interfaces::msg::IoCmd>(
    "io_cmd", rclcpp::SensorDataQoS(),
    std::bind(&CanControl::io_cmd_callback, this, std::placeholders::_1));

  ctrl_cmd_subscriber_ = node_->create_subscription<yhs_can_interfaces::msg::CtrlCmd>(
    "ctrl_cmd", rclcpp::SensorDataQoS(),
    std::bind(&CanControl::ctrl_cmd_callback, this, std::placeholders::_1));

  const auto send_period = std::chrono::duration<double>(1.0 / control_config.send_rate_hz);
  ctrl_send_timer_ = node_->create_wall_timer(
    std::chrono::duration_cast<std::chrono::nanoseconds>(send_period),
    std::bind(&CanControl::send_control_command, this));

  chassis_info_fb_publisher_ =
    node_->create_publisher<yhs_can_interfaces::msg::ChassisInfoFb>("chassis_info_fb", 10);
  veh_diag_fb_publisher_ =
    node_->create_publisher<yhs_can_interfaces::msg::VehDiagFb>("veh_diag_fb", 10);
  odom_pub_ = node_->create_publisher<nav_msgs::msg::Odometry>("odom", 10);
  tf_broadcaster_ = std::make_unique<tf2_ros::TransformBroadcaster>(node_);
}

CanControl::~CanControl()
{
  stop();
}

bool CanControl::validate_ultrasonic_mapping() const
{
  if (ultrasonic_number_.size() != ultrasonic_data_.size()) {
    return false;
  }
  for (const auto index : ultrasonic_number_) {
    if (index < 0 || index >= static_cast<int64_t>(ultrasonic_data_.size())) {
      return false;
    }
  }
  return true;
}

void CanControl::io_cmd_callback(const yhs_can_interfaces::msg::IoCmd::SharedPtr io_cmd_msg)
{
  // 把 ROS 消息字段搬到协议层结构体，再统一编码成厂家 CAN 帧。
  mk_mini::IoCommand command;
  command.enable = io_cmd_msg->io_cmd_enable;
  command.lower_beam_headlamp = io_cmd_msg->io_cmd_lower_beam_headlamp;
  command.upper_beam_headlamp = io_cmd_msg->io_cmd_upper_beam_headlamp;
  command.turn_lamp = io_cmd_msg->io_cmd_turn_lamp;
  command.braking_lamp = io_cmd_msg->io_cmd_braking_lamp;
  command.clearance_lamp = io_cmd_msg->io_cmd_clearance_lamp;
  command.fog_lamp = io_cmd_msg->io_cmd_fog_lamp;
  command.speaker = io_cmd_msg->io_cmd_speaker;
  command.dis_charge = io_cmd_msg->io_cmd_dis_charge;

  io_alive_count_ = static_cast<std::uint8_t>((io_alive_count_ + 1) & 0x0f);
  write_frame(mk_mini::kIoCmdId, mk_mini::encodeIoCommand(command, io_alive_count_));
}

void CanControl::ctrl_cmd_callback(const yhs_can_interfaces::msg::CtrlCmd::SharedPtr ctrl_cmd_msg)
{
  mk_mini::CtrlCommand command;
  command.gear = ctrl_cmd_msg->ctrl_cmd_gear;
  command.velocity_mps = ctrl_cmd_msg->ctrl_cmd_velocity;
  command.steering_deg = ctrl_cmd_msg->ctrl_cmd_steering;

  std::lock_guard<std::mutex> lock(control_command_gate_mutex_);
  control_command_gate_.update(command, steady_now_sec());
}

void CanControl::send_control_command()
{
  mk_mini::CtrlCommand command;
  {
    std::lock_guard<std::mutex> lock(control_command_gate_mutex_);
    command = control_command_gate_.command_for_send(steady_now_sec());
  }
  ctrl_alive_count_ = static_cast<std::uint8_t>((ctrl_alive_count_ + 1) & 0x0f);
  write_frame(mk_mini::kCtrlCmdId, mk_mini::encodeCtrlCommand(command, ctrl_alive_count_));
}

bool CanControl::write_frame(const std::uint32_t can_id, const mk_mini::FrameData & data)
{
  // 多个 ROS 回调都可能写 CAN，因此写 socket 时加锁。
  std::lock_guard<std::mutex> lock(socket_mutex_);
  if (can_socket_ < 0) {
    RCLCPP_WARN_THROTTLE(
      node_->get_logger(), *node_->get_clock(), 2000, "CAN socket 未打开，丢弃该帧。");
    return false;
  }

  can_frame frame{};
  frame.can_id = socketcan::make_extended_can_id(can_id);
  frame.can_dlc = static_cast<__u8>(data.size());
  std::memcpy(frame.data, data.data(), data.size());

  const auto written = ::write(can_socket_, &frame, sizeof(frame));
  if (written != static_cast<ssize_t>(sizeof(frame))) {
    RCLCPP_ERROR_STREAM(
      node_->get_logger(), "发送 CAN 帧失败 0x" << std::hex << can_id << "：" <<
        std::strerror(errno));
    return false;
  }
  return true;
}

bool CanControl::wait_for_can_frame()
{
  if (can_socket_ < 0) {
    return false;
  }

  timeval tv{};
  // select 使用短超时，让 stop() 后接收线程能尽快退出。
  tv.tv_usec = 30000;

  fd_set rdfs;
  FD_ZERO(&rdfs);
  FD_SET(can_socket_, &rdfs);

  const int ret = ::select(can_socket_ + 1, &rdfs, nullptr, nullptr, &tv);
  if (ret < 0) {
    if (running_) {
      RCLCPP_ERROR_STREAM_THROTTLE(
        node_->get_logger(), *node_->get_clock(), 2000,
        "等待 CAN 帧时出错：" << std::strerror(errno));
    }
    return false;
  }
  if (ret == 0) {
    RCLCPP_WARN_THROTTLE(
      node_->get_logger(), *node_->get_clock(), 5000,
      "未收到 CAN 帧。请检查 CAN 接口、接线和底盘电源。");
    return false;
  }
  return true;
}

void CanControl::publish_chassis_info()
{
  // 所有反馈帧都聚合进同一个 ChassisInfoFb，便于上层只订阅一个 topic。
  chassis_info_msg_.header.stamp = node_->get_clock()->now();
  chassis_info_fb_publisher_->publish(chassis_info_msg_);
}

void CanControl::can_data_recv_callback()
{
  // 接收线程只负责读 CAN 和更新反馈消息；ROS spin 仍在主线程运行。
  while (running_ && rclcpp::ok()) {
    if (!wait_for_can_frame()) {
      continue;
    }

    can_frame recv_frame{};
    {
      std::lock_guard<std::mutex> lock(socket_mutex_);
      if (can_socket_ < 0) {
        continue;
      }
      const auto received = ::read(can_socket_, &recv_frame, sizeof(recv_frame));
      if (received != static_cast<ssize_t>(sizeof(recv_frame))) {
        if (running_) {
          RCLCPP_ERROR_STREAM_THROTTLE(
            node_->get_logger(), *node_->get_clock(), 2000,
            "读取 CAN 帧失败：" << std::strerror(errno));
        }
        continue;
      }
    }

    const auto data = frame_data_from_can(recv_frame);
    const auto protocol_can_id = socketcan::normalize_received_can_id(recv_frame.can_id);
    // 按 CAN ID 分发到对应协议解析函数；校验失败的帧会返回空值并被丢弃。
    switch (protocol_can_id) {
      case mk_mini::kCtrlFbId: {
          const auto feedback = mk_mini::decodeCtrlFeedback(data);
          if (!feedback) {
            break;
          }
          yhs_can_interfaces::msg::CtrlFb msg;
          msg.ctrl_fb_gear = feedback->gear;
          msg.ctrl_fb_velocity = static_cast<float>(feedback->velocity_mps);
          msg.ctrl_fb_steering = static_cast<float>(feedback->steering_deg);
          msg.ctrl_fb_mode = feedback->mode;
          chassis_info_msg_.ctrl_fb = msg;
          publish_chassis_info();

          // 如果底盘还没有发送 ODO 反馈，先用速度反馈做里程计积分，保证 /odom 有基础输出。
          if (!have_odo_feedback_) {
            const double signed_velocity = (feedback->gear == 2) ?
              -feedback->velocity_mps : feedback->velocity_mps;
            publish_integrated_odom(signed_velocity, feedback->steering_deg * kDegToRad);
          }
          break;
        }
      case mk_mini::kLrWheelFbId: {
          const auto feedback = mk_mini::decodeWheelFeedback(data);
          if (!feedback) {
            break;
          }
          yhs_can_interfaces::msg::LrWheelFb msg;
          msg.lr_wheel_fb_velocity = static_cast<float>(feedback->velocity_mps);
          msg.lr_wheel_fb_pulse = feedback->pulse;
          chassis_info_msg_.lr_wheel_fb = msg;
          publish_chassis_info();
          break;
        }
      case mk_mini::kRrWheelFbId: {
          const auto feedback = mk_mini::decodeWheelFeedback(data);
          if (!feedback) {
            break;
          }
          yhs_can_interfaces::msg::RrWheelFb msg;
          msg.rr_wheel_fb_velocity = static_cast<float>(feedback->velocity_mps);
          msg.rr_wheel_fb_pulse = feedback->pulse;
          chassis_info_msg_.rr_wheel_fb = msg;
          publish_chassis_info();
          break;
        }
      case mk_mini::kIoFbId: {
          const auto feedback = mk_mini::decodeIoFeedback(data);
          if (!feedback) {
            break;
          }
          yhs_can_interfaces::msg::IoFb msg;
          msg.io_fb_enable = feedback->enable;
          msg.io_fb_turn_lamp = feedback->turn_lamp;
          msg.io_fb_braking_lamp = feedback->braking_lamp;
          msg.io_fb_fm_impact_sensor = feedback->fm_impact_sensor;
          msg.io_fb_rm_impact_sensor = feedback->rm_impact_sensor;
          msg.io_fb_dis_charge = feedback->dis_charge;
          msg.io_fb_charge_en = feedback->charge_en;
          msg.io_fb_scram_st = feedback->scram_st;
          chassis_info_msg_.io_fb = msg;
          publish_chassis_info();
          break;
        }
      case mk_mini::kBmsInfoFbId: {
          const auto feedback = mk_mini::decodeBmsInfoFeedback(data);
          if (!feedback) {
            break;
          }
          yhs_can_interfaces::msg::BmsInfoFb msg;
          msg.bms_info_voltage = static_cast<float>(feedback->voltage);
          msg.bms_info_current = static_cast<float>(feedback->current);
          msg.bms_info_remaining_capacity = static_cast<float>(feedback->remaining_capacity);
          chassis_info_msg_.bms_info_fb = msg;
          publish_chassis_info();
          break;
        }
      case mk_mini::kBmsFlagInfoFbId: {
          const auto feedback = mk_mini::decodeBmsFlagInfoFeedback(data);
          if (!feedback) {
            break;
          }
          yhs_can_interfaces::msg::BmsFlagInfoFb msg;
          msg.bms_flag_info_soc = feedback->soc;
          msg.bms_flag_info_single_ov = feedback->single_ov;
          msg.bms_flag_info_single_uv = feedback->single_uv;
          msg.bms_flag_info_ov = feedback->ov;
          msg.bms_flag_info_uv = feedback->uv;
          msg.bms_flag_info_charge_ot = feedback->charge_ot;
          msg.bms_flag_info_charge_ut = feedback->charge_ut;
          msg.bms_flag_info_discharge_ot = feedback->discharge_ot;
          msg.bms_flag_info_discharge_ut = feedback->discharge_ut;
          msg.bms_flag_info_charge_oc = feedback->charge_oc;
          msg.bms_flag_info_discharge_oc = feedback->discharge_oc;
          msg.bms_flag_info_short = feedback->short_fault;
          msg.bms_flag_info_ic_error = feedback->ic_error;
          msg.bms_flag_info_lock_mos = feedback->lock_mos;
          msg.bms_flag_info_charge_flag = feedback->charge_flag;
          msg.bms_flag_info_soc_warning = feedback->soc_warning;
          msg.bms_flag_info_soc_low_protection = feedback->soc_low_protection;
          msg.bms_flag_info_hight_temperature = static_cast<float>(feedback->high_temperature);
          msg.bms_flag_info_low_temperature = static_cast<float>(feedback->low_temperature);
          chassis_info_msg_.bms_flag_info_fb = msg;
          publish_chassis_info();
          break;
        }
      case mk_mini::kDriveMcuEcodeFbId: {
          const auto feedback = mk_mini::decodeDriveMcuEcodeFeedback(data);
          if (!feedback) {
            break;
          }
          yhs_can_interfaces::msg::DriveMcuEcodeFb msg;
          msg.drive_fb_mcuecode = feedback->ecode;
          chassis_info_msg_.drive_mcu_ecode_fb = msg;
          publish_chassis_info();
          break;
        }
      case mk_mini::kVehDiagFbId: {
          const auto feedback = mk_mini::decodeVehDiagFeedback(data);
          if (!feedback) {
            break;
          }
          yhs_can_interfaces::msg::VehDiagFb msg;
          msg.veh_fb_fault_level = feedback->fault_level;
          msg.veh_fb_auto_can_ctrl_cmd = feedback->auto_can_ctrl_cmd;
          msg.veh_fb_auto_io_can_cmd = feedback->auto_io_can_cmd;
          msg.veh_fb_eps_dis_on_line = feedback->eps_dis_on_line;
          msg.veh_fb_eps_fault = feedback->eps_fault;
          msg.veh_fb_eps_mosf_et_ot = feedback->eps_mosfet_ot;
          msg.veh_fb_eps_warning = feedback->eps_warning;
          msg.veh_fb_eps_dis_work = feedback->eps_dis_work;
          msg.veh_fb_eps_over_current = feedback->eps_over_current;
          msg.veh_fb_ehb_ecu_fault = feedback->ehb_ecu_fault;
          msg.veh_fb_ehb_dis_on_line = feedback->ehb_dis_on_line;
          msg.veh_fb_ehb_work_model_fault = feedback->ehb_work_model_fault;
          msg.veh_fb_ehb_dis_en = feedback->ehb_dis_en;
          msg.veh_fb_ehb_anguler_fault = feedback->ehb_anguler_fault;
          msg.veh_fb_ehb_ot = feedback->ehb_ot;
          msg.veh_fb_ehb_power_fault = feedback->ehb_power_fault;
          msg.veh_fb_ehb_sensor_abnomal = feedback->ehb_sensor_abnormal;
          msg.veh_fb_ehb_motor_fault = feedback->ehb_motor_fault;
          msg.veh_fb_ehb_oil_press_sensor_fault = feedback->ehb_oil_press_sensor_fault;
          msg.veh_fb_ehb_oil_fault = feedback->ehb_oil_fault;
          msg.veh_fb_ld_rv_mcu_fault = feedback->left_drive_mcu_fault;
          msg.veh_fb_rd_rv_mcu_fault = feedback->right_drive_mcu_fault;
          msg.veh_fb_aux_bms_dis_on_line = feedback->aux_bms_dis_on_line;
          msg.veh_fb_aux_scram = feedback->aux_scram;
          msg.veh_fb_aux_remote_close = feedback->aux_remote_close;
          msg.veh_fb_aux_remote_dis_on_line = feedback->aux_remote_dis_on_line;
          chassis_info_msg_.veh_diag_fb = msg;
          veh_diag_fb_publisher_->publish(msg);
          publish_chassis_info();
          break;
        }
      case mk_mini::kOdoFbId: {
          const auto feedback = mk_mini::decodeOdoFeedback(data);
          if (!feedback) {
            break;
          }
          yhs_can_interfaces::msg::OdoFb msg;
          msg.odo_fb_accumulative_mileage =
            static_cast<float>(feedback->accumulative_mileage_m);
          msg.odo_fb_accumulative_angular =
            static_cast<float>(feedback->accumulative_angular_rad);
          chassis_info_msg_.odo_fb = msg;
          publish_chassis_info();
          // 一旦收到厂家 ODO 帧，就优先用底盘累计里程发布 /odom。
          publish_odo_feedback_odom(*feedback);
          break;
        }
      case mk_mini::kUltrasonic1FbId: {
          const auto group = mk_mini::decodeUltrasonicGroup(data);
          std::copy(group.begin(), group.end(), ultrasonic_data_.begin());
          break;
        }
      case mk_mini::kUltrasonic2FbId: {
          const auto group = mk_mini::decodeUltrasonicGroup(data);
          std::copy(group.begin(), group.end(), ultrasonic_data_.begin() + 4);
          yhs_can_interfaces::msg::Ultrasonic msg;
          // 两个超声波反馈帧凑齐后，再按用户配置的顺序映射到前后左右方位。
          msg.front_right = ultrasonic_data_[ultrasonic_number_[0]];
          msg.front_left = ultrasonic_data_[ultrasonic_number_[1]];
          msg.left_front = ultrasonic_data_[ultrasonic_number_[2]];
          msg.left_rear = ultrasonic_data_[ultrasonic_number_[3]];
          msg.rear_left = ultrasonic_data_[ultrasonic_number_[4]];
          msg.rear_right = ultrasonic_data_[ultrasonic_number_[5]];
          msg.right_rear = ultrasonic_data_[ultrasonic_number_[6]];
          msg.right_front = ultrasonic_data_[ultrasonic_number_[7]];
          chassis_info_msg_.ultrasonic = msg;
          publish_chassis_info();
          break;
        }
      default:
        break;
    }
  }
}

void CanControl::publish_integrated_odom(const double velocity_mps, const double steering_rad)
{
  // 回退方案：用 Ackermann 模型按速度和转角积分。精度取决于速度反馈和 wheel_base 参数。
  const auto current_time = node_->now();
  if (!have_odom_time_) {
    last_odom_time_ = current_time;
    have_odom_time_ = true;
    return;
  }

  const double dt = (current_time - last_odom_time_).seconds();
  if (dt <= 0.0) {
    return;
  }

  const double angular_velocity = velocity_mps * std::tan(steering_rad) / wheel_base_;
  x_ += velocity_mps * std::cos(theta_) * dt;
  y_ += velocity_mps * std::sin(theta_) * dt;
  theta_ += angular_velocity * dt;
  last_odom_time_ = current_time;

  publish_odom_message(current_time, velocity_mps, angular_velocity);
}

void CanControl::publish_odo_feedback_odom(const mk_mini::OdoFeedback & feedback)
{
  // 首选方案：使用底盘累计里程和累计航向角，减少单纯速度积分造成的漂移。
  const auto current_time = node_->now();
  double linear_velocity = 0.0;
  double angular_velocity = 0.0;

  if (have_odo_feedback_ && have_odom_time_) {
    const double dt = (current_time - last_odom_time_).seconds();
    if (dt > 0.0) {
      const double delta_mileage = feedback.accumulative_mileage_m - last_odo_mileage_;
      const double delta_heading = feedback.accumulative_angular_rad - last_odo_heading_;
      linear_velocity = delta_mileage / dt;
      angular_velocity = delta_heading / dt;
      theta_ = feedback.accumulative_angular_rad;
      x_ += delta_mileage * std::cos(theta_);
      y_ += delta_mileage * std::sin(theta_);
    }
  } else {
    theta_ = feedback.accumulative_angular_rad;
    have_odo_feedback_ = true;
  }

  last_odo_mileage_ = feedback.accumulative_mileage_m;
  last_odo_heading_ = feedback.accumulative_angular_rad;
  last_odom_time_ = current_time;
  have_odom_time_ = true;
  publish_odom_message(current_time, linear_velocity, angular_velocity);
}

void CanControl::publish_odom_message(
  const rclcpp::Time & stamp, const double linear_velocity, const double angular_velocity)
{
  // ROS 标准里程计消息：父坐标系 odom，子坐标系 base_link。
  nav_msgs::msg::Odometry odom_msg;
  odom_msg.header.stamp = stamp;
  odom_msg.header.frame_id = odom_frame_id_;
  odom_msg.child_frame_id = base_frame_id_;

  odom_msg.pose.pose.position.x = x_;
  odom_msg.pose.pose.position.y = y_;
  odom_msg.pose.pose.position.z = 0.0;

  tf2::Quaternion quat;
  quat.setRPY(0.0, 0.0, theta_);
  odom_msg.pose.pose.orientation.x = quat.x();
  odom_msg.pose.pose.orientation.y = quat.y();
  odom_msg.pose.pose.orientation.z = quat.z();
  odom_msg.pose.pose.orientation.w = quat.w();

  odom_msg.twist.twist.linear.x = linear_velocity;
  odom_msg.twist.twist.angular.z = angular_velocity;
  odom_pub_->publish(odom_msg);

  if (publish_odom_tf_) {
    // Nav2 通常需要 odom -> base_link TF；如果外部定位也发布同名 TF，应关闭此参数。
    geometry_msgs::msg::TransformStamped transform;
    transform.header.stamp = stamp;
    transform.header.frame_id = odom_frame_id_;
    transform.child_frame_id = base_frame_id_;
    transform.transform.translation.x = x_;
    transform.transform.translation.y = y_;
    transform.transform.translation.z = 0.0;
    transform.transform.rotation = odom_msg.pose.pose.orientation;
    tf_broadcaster_->sendTransform(transform);
  }
}

bool CanControl::run()
{
  // 使用 Linux SocketCAN 打开 canX，要求系统已提前配置并启动对应 CAN 接口。
  can_socket_ = ::socket(PF_CAN, SOCK_RAW, CAN_RAW);
  if (can_socket_ < 0) {
    RCLCPP_ERROR_STREAM(node_->get_logger(), "打开 CAN socket 失败：" << std::strerror(errno));
    return false;
  }

  ifreq ifr{};
  std::strncpy(ifr.ifr_name, if_name_.c_str(), IFNAMSIZ - 1);
  if (ioctl(can_socket_, SIOCGIFINDEX, &ifr) < 0) {
    RCLCPP_ERROR_STREAM(
      node_->get_logger(), "获取 CAN 接口索引失败，接口 " << if_name_ << "：" <<
        std::strerror(errno));
    stop();
    return false;
  }

  sockaddr_can addr{};
  addr.can_family = AF_CAN;
  addr.can_ifindex = ifr.ifr_ifindex;
  if (bind(can_socket_, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) < 0) {
    RCLCPP_ERROR_STREAM(node_->get_logger(), "绑定 CAN socket 失败：" << std::strerror(errno));
    stop();
    return false;
  }

  running_ = true;
  // 接收 CAN 是阻塞/等待型工作，放到独立线程，避免卡住 ROS 回调。
  thread_ = std::thread(&CanControl::can_data_recv_callback, this);
  return true;
}

void CanControl::stop()
{
  // 先通知接收循环退出，再关闭 socket；shutdown 可唤醒正在 select/read 的线程。
  running_ = false;
  {
    std::lock_guard<std::mutex> lock(socket_mutex_);
    if (can_socket_ >= 0) {
      ::shutdown(can_socket_, SHUT_RDWR);
      ::close(can_socket_);
      can_socket_ = -1;
    }
  }

  if (thread_.joinable()) {
    thread_.join();
  }
}

}  // namespace yhs

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("yhs_can_control_node");

  try {
    yhs::CanControl cancontrol(node);
    if (!cancontrol.run()) {
      RCLCPP_ERROR(node->get_logger(), "初始化 yhs_can_control_node 失败");
      rclcpp::shutdown();
      return 1;
    }

    RCLCPP_INFO(node->get_logger(), "yhs_can_control_node 初始化成功");
    rclcpp::spin(node);
    cancontrol.stop();
  } catch (const std::exception & ex) {
    RCLCPP_FATAL(node->get_logger(), "启动 yhs_can_control_node 失败：%s", ex.what());
    rclcpp::shutdown();
    return 1;
  }

  RCLCPP_INFO(node->get_logger(), "yhs_can_control_node 已停止");
  rclcpp::shutdown();
  return 0;
}
