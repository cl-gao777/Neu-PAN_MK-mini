#ifndef YHS_CAN_CONTROL_MK_MINI_PROTOCOL_HPP_
#define YHS_CAN_CONTROL_MK_MINI_PROTOCOL_HPP_

#include <array>
#include <cstdint>
#include <optional>

namespace yhs::mk_mini
{

// MK-mini 每个 CAN 数据帧固定使用 8 字节，这里统一用 FrameData 表示 data[0]~data[7]。
using FrameData = std::array<std::uint8_t, 8>;

// 厂家 DBC 中定义的扩展帧 ID。命名规则：
// Cmd 表示上位机发给底盘的指令，Fb 表示底盘反馈给上位机的数据。
constexpr std::uint32_t kCtrlCmdId = 0x98C4D2D0;
constexpr std::uint32_t kIoCmdId = 0x98C4D7D0;
constexpr std::uint32_t kCtrlFbId = 0x98C4D2EF;
constexpr std::uint32_t kLrWheelFbId = 0x98C4D7EF;
constexpr std::uint32_t kRrWheelFbId = 0x98C4D8EF;
constexpr std::uint32_t kIoFbId = 0x98C4DAEF;
constexpr std::uint32_t kDriveMcuEcodeFbId = 0x98C4DCEF;
constexpr std::uint32_t kOdoFbId = 0x98C4DEEF;
constexpr std::uint32_t kBmsInfoFbId = 0x98C4E1EF;
constexpr std::uint32_t kBmsFlagInfoFbId = 0x98C4E2EF;
constexpr std::uint32_t kUltrasonic1FbId = 0x98C4E8EF;
constexpr std::uint32_t kUltrasonic2FbId = 0x98C4E9EF;
constexpr std::uint32_t kVehDiagFbId = 0x98C4EAEF;

struct CtrlCommand
{
  // gear 是底盘挡位；velocity_mps 单位 m/s；steering_deg 单位度。
  std::uint8_t gear{0};
  double velocity_mps{0.0};
  double steering_deg{0.0};
  std::uint8_t brake{0};
};

struct IoCommand
{
  // IO 指令控制灯光、喇叭、放电等辅助功能。
  bool enable{false};
  bool lower_beam_headlamp{false};
  bool upper_beam_headlamp{false};
  std::uint8_t turn_lamp{0};
  bool braking_lamp{false};
  bool clearance_lamp{false};
  bool fog_lamp{false};
  bool speaker{false};
  bool dis_charge{false};
};

struct CtrlFeedback
{
  // 底盘实际控制反馈：挡位、速度、转角和控制模式。
  std::uint8_t gear{0};
  double velocity_mps{0.0};
  double steering_deg{0.0};
  std::uint8_t mode{0};
};

struct WheelFeedback
{
  // 单侧后轮反馈：轮速和编码器脉冲。
  double velocity_mps{0.0};
  std::int32_t pulse{0};
};

struct IoFeedback
{
  bool enable{false};
  std::uint8_t turn_lamp{0};
  bool braking_lamp{false};
  bool fm_impact_sensor{false};
  bool rm_impact_sensor{false};
  bool dis_charge{false};
  bool charge_en{false};
  bool scram_st{false};
};

struct BmsInfoFeedback
{
  double voltage{0.0};
  double current{0.0};
  double remaining_capacity{0.0};
};

struct BmsFlagInfoFeedback
{
  // BMS 状态位较多，bool 字段表示对应故障/告警位是否置位。
  std::uint8_t soc{0};
  bool single_ov{false};
  bool single_uv{false};
  bool ov{false};
  bool uv{false};
  bool charge_ot{false};
  bool charge_ut{false};
  bool discharge_ot{false};
  bool discharge_ut{false};
  bool charge_oc{false};
  bool discharge_oc{false};
  bool short_fault{false};
  bool ic_error{false};
  bool lock_mos{false};
  bool charge_flag{false};
  bool soc_warning{false};
  bool soc_low_protection{false};
  double high_temperature{0.0};
  double low_temperature{0.0};
};

struct DriveMcuEcodeFeedback
{
  std::int32_t ecode{0};
};

struct VehDiagFeedback
{
  // 整车诊断反馈：包含 EPS、EHB、驱动 MCU、急停和遥控等状态。
  std::uint8_t fault_level{0};
  bool auto_can_ctrl_cmd{false};
  bool auto_io_can_cmd{false};
  bool eps_dis_on_line{false};
  bool eps_fault{false};
  bool eps_mosfet_ot{false};
  bool eps_warning{false};
  bool eps_dis_work{false};
  bool eps_over_current{false};
  bool ehb_ecu_fault{false};
  bool ehb_dis_on_line{false};
  bool ehb_work_model_fault{false};
  bool ehb_dis_en{false};
  bool ehb_anguler_fault{false};
  bool ehb_ot{false};
  bool ehb_power_fault{false};
  bool ehb_sensor_abnormal{false};
  bool ehb_motor_fault{false};
  bool ehb_oil_press_sensor_fault{false};
  bool ehb_oil_fault{false};
  std::uint8_t left_drive_mcu_fault{0};
  std::uint8_t right_drive_mcu_fault{0};
  bool aux_bms_dis_on_line{false};
  bool aux_scram{false};
  bool aux_remote_close{false};
  bool aux_remote_dis_on_line{false};
};

struct OdoFeedback
{
  // 底盘累计里程和累计航向角；代码中优先用它发布 /odom。
  double accumulative_mileage_m{0.0};
  double accumulative_angular_rad{0.0};
};

std::uint8_t checksum(const FrameData & data);
bool hasValidChecksum(const FrameData & data);

// 编码函数把 ROS 层的物理量转换为 DBC 定义的原始字节。
FrameData encodeCtrlCommand(const CtrlCommand & command, std::uint8_t alive_count);
FrameData encodeIoCommand(const IoCommand & command, std::uint8_t alive_count);

// 解码函数先检查校验，失败返回 std::nullopt，避免把坏帧发布到 ROS topic。
std::optional<CtrlFeedback> decodeCtrlFeedback(const FrameData & data);
std::optional<WheelFeedback> decodeWheelFeedback(const FrameData & data);
std::optional<IoFeedback> decodeIoFeedback(const FrameData & data);
std::optional<BmsInfoFeedback> decodeBmsInfoFeedback(const FrameData & data);
std::optional<BmsFlagInfoFeedback> decodeBmsFlagInfoFeedback(const FrameData & data);
std::optional<DriveMcuEcodeFeedback> decodeDriveMcuEcodeFeedback(const FrameData & data);
std::optional<VehDiagFeedback> decodeVehDiagFeedback(const FrameData & data);
std::optional<OdoFeedback> decodeOdoFeedback(const FrameData & data);

// 两个超声波 CAN 帧各带 4 个传感器距离，单位由厂家协议定义。
std::array<std::uint16_t, 4> decodeUltrasonicGroup(const FrameData & data);

}  // namespace yhs::mk_mini

#endif  // YHS_CAN_CONTROL_MK_MINI_PROTOCOL_HPP_
