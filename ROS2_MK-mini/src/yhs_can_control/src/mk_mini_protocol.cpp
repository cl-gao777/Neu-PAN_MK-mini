#include "yhs_can_control/mk_mini_protocol.hpp"

#include <algorithm>
#include <cmath>

// 这个文件只负责 MK-mini CAN 协议的字节级编解码，不直接接触 ROS topic。

namespace yhs::mk_mini
{
namespace
{

std::uint8_t nextAliveNibble(const std::uint8_t alive_count)
{
  // 协议把 4-bit alive counter 放在 data[6] 的高 4 位，用来让底盘判断指令是否持续更新。
  return static_cast<std::uint8_t>((alive_count & 0x0f) << 4);
}

std::int16_t signExtend12(const std::uint16_t value)
{
  // BMS 温度是 12-bit 有符号数，先保留低 12 位，再把符号位扩展到 int16。
  const std::uint16_t masked = value & 0x0fff;
  return static_cast<std::int16_t>((masked & 0x0800) ? (masked | 0xf000) : masked);
}

std::int16_t toInt16(const std::uint16_t value)
{
  return static_cast<std::int16_t>(value);
}

std::int32_t toInt32(
  const std::uint8_t b0, const std::uint8_t b1, const std::uint8_t b2, const std::uint8_t b3)
{
  // DBC 中多字节整数按小端排列：低字节在前，高字节在后。
  const std::uint32_t raw =
    static_cast<std::uint32_t>(b0) |
    (static_cast<std::uint32_t>(b1) << 8) |
    (static_cast<std::uint32_t>(b2) << 16) |
    (static_cast<std::uint32_t>(b3) << 24);
  return static_cast<std::int32_t>(raw);
}

std::uint16_t saturatedUnsigned16(const double scaled)
{
  // 发送到底盘前先做饱和，防止 NaN、负数或过大值溢出到 CAN 原始字段。
  if (!std::isfinite(scaled) || scaled <= 0.0) {
    return 0;
  }
  if (scaled >= 65535.0) {
    return 65535;
  }
  return static_cast<std::uint16_t>(std::lround(scaled));
}

std::int16_t saturatedSigned16(const double scaled)
{
  if (!std::isfinite(scaled)) {
    return 0;
  }
  if (scaled <= -32768.0) {
    return -32768;
  }
  if (scaled >= 32767.0) {
    return 32767;
  }
  return static_cast<std::int16_t>(std::lround(scaled));
}

}  // namespace

std::uint8_t checksum(const FrameData & data)
{
  // 厂家协议使用前 7 个字节异或作为 BCC 校验，结果放在 data[7]。
  return static_cast<std::uint8_t>(
    data[0] ^ data[1] ^ data[2] ^ data[3] ^ data[4] ^ data[5] ^ data[6]);
}

bool hasValidChecksum(const FrameData & data)
{
  return checksum(data) == data[7];
}

FrameData encodeCtrlCommand(const CtrlCommand & command, const std::uint8_t alive_count)
{
  FrameData data{};
  // DBC 缩放：速度 m/s * 1000，转角 deg * 100，编码为原始整数。
  const std::uint16_t velocity = saturatedUnsigned16(command.velocity_mps * 1000.0);
  const std::uint16_t steering =
    static_cast<std::uint16_t>(saturatedSigned16(command.steering_deg * 100.0));
  const std::uint8_t brake = static_cast<std::uint8_t>(std::min<int>(command.brake, 127));

  data[0] = static_cast<std::uint8_t>((command.gear & 0x0f) | ((velocity & 0x000f) << 4));
  data[1] = static_cast<std::uint8_t>((velocity >> 4) & 0xff);
  data[2] = static_cast<std::uint8_t>(((velocity >> 12) & 0x0f) | ((steering & 0x000f) << 4));
  data[3] = static_cast<std::uint8_t>((steering >> 4) & 0xff);
  data[4] = static_cast<std::uint8_t>(((steering >> 12) & 0x0f) | ((brake & 0x0f) << 4));
  data[5] = static_cast<std::uint8_t>((brake >> 4) & 0x0f);
  data[6] = nextAliveNibble(alive_count);
  data[7] = checksum(data);
  return data;
}

FrameData encodeIoCommand(const IoCommand & command, const std::uint8_t alive_count)
{
  FrameData data{};
  data[0] = command.enable ? 1 : 0;
  if (command.lower_beam_headlamp) {
    data[1] |= 0x01;
  }
  if (command.upper_beam_headlamp) {
    data[1] |= 0x02;
  }
  data[1] |= static_cast<std::uint8_t>((command.turn_lamp & 0x03) << 2);
  if (command.braking_lamp) {
    data[1] |= 0x10;
  }
  if (command.clearance_lamp) {
    data[1] |= 0x20;
  }
  if (command.fog_lamp) {
    data[1] |= 0x40;
  }
  data[2] = command.speaker ? 1 : 0;
  data[5] = command.dis_charge ? 1 : 0;
  data[6] = nextAliveNibble(alive_count);
  data[7] = checksum(data);
  return data;
}

std::optional<CtrlFeedback> decodeCtrlFeedback(const FrameData & data)
{
  if (!hasValidChecksum(data)) {
    // 校验失败通常表示帧损坏或协议版本不匹配，直接丢弃更安全。
    return std::nullopt;
  }
  CtrlFeedback feedback;
  feedback.gear = data[0] & 0x0f;
  const std::uint16_t velocity_raw = static_cast<std::uint16_t>(
    ((data[2] & 0x0f) << 12) | (data[1] << 4) | ((data[0] & 0xf0) >> 4));
  const std::uint16_t steering_raw = static_cast<std::uint16_t>(
    ((data[4] & 0x0f) << 12) | (data[3] << 4) | ((data[2] & 0xf0) >> 4));
  feedback.velocity_mps = static_cast<double>(velocity_raw) / 1000.0;
  feedback.steering_deg = static_cast<double>(toInt16(steering_raw)) / 100.0;
  feedback.mode = static_cast<std::uint8_t>((data[5] & 0x30) >> 4);
  return feedback;
}

std::optional<WheelFeedback> decodeWheelFeedback(const FrameData & data)
{
  if (!hasValidChecksum(data)) {
    return std::nullopt;
  }
  WheelFeedback feedback;
  const std::uint16_t velocity_raw = static_cast<std::uint16_t>(data[0] | (data[1] << 8));
  feedback.velocity_mps = static_cast<double>(toInt16(velocity_raw)) / 1000.0;
  feedback.pulse = toInt32(data[2], data[3], data[4], data[5]);
  return feedback;
}

std::optional<IoFeedback> decodeIoFeedback(const FrameData & data)
{
  if (!hasValidChecksum(data)) {
    return std::nullopt;
  }
  IoFeedback feedback;
  feedback.enable = (data[0] & 0x01) != 0;
  feedback.turn_lamp = static_cast<std::uint8_t>((data[1] & 0x0c) >> 2);
  feedback.braking_lamp = (data[1] & 0x10) != 0;
  feedback.fm_impact_sensor = (data[3] & 0x02) != 0;
  feedback.rm_impact_sensor = (data[3] & 0x10) != 0;
  feedback.dis_charge = (data[5] & 0x01) != 0;
  feedback.charge_en = (data[5] & 0x02) != 0;
  feedback.scram_st = (data[5] & 0x10) != 0;
  return feedback;
}

std::optional<BmsInfoFeedback> decodeBmsInfoFeedback(const FrameData & data)
{
  if (!hasValidChecksum(data)) {
    return std::nullopt;
  }
  BmsInfoFeedback feedback;
  feedback.voltage = static_cast<double>(data[0] | (data[1] << 8)) / 100.0;
  feedback.current = static_cast<double>(toInt16(data[2] | (data[3] << 8))) / 100.0;
  feedback.remaining_capacity = static_cast<double>(data[4] | (data[5] << 8)) / 100.0;
  return feedback;
}

std::optional<BmsFlagInfoFeedback> decodeBmsFlagInfoFeedback(const FrameData & data)
{
  if (!hasValidChecksum(data)) {
    return std::nullopt;
  }
  BmsFlagInfoFeedback feedback;
  feedback.soc = data[0];
  feedback.single_ov = (data[1] & 0x01) != 0;
  feedback.single_uv = (data[1] & 0x02) != 0;
  feedback.ov = (data[1] & 0x04) != 0;
  feedback.uv = (data[1] & 0x08) != 0;
  feedback.charge_ot = (data[1] & 0x10) != 0;
  feedback.charge_ut = (data[1] & 0x20) != 0;
  feedback.discharge_ot = (data[1] & 0x40) != 0;
  feedback.discharge_ut = (data[1] & 0x80) != 0;
  feedback.charge_oc = (data[2] & 0x01) != 0;
  feedback.discharge_oc = (data[2] & 0x02) != 0;
  feedback.short_fault = (data[2] & 0x04) != 0;
  feedback.ic_error = (data[2] & 0x08) != 0;
  feedback.lock_mos = (data[2] & 0x10) != 0;
  feedback.charge_flag = (data[2] & 0x20) != 0;
  feedback.soc_warning = (data[2] & 0x40) != 0;
  feedback.soc_low_protection = (data[2] & 0x80) != 0;

  // 高低温字段跨字节且是 12-bit 有符号数，不能按普通 uint16 直接解释。
  const std::uint16_t high_raw = static_cast<std::uint16_t>((data[4] << 4) | (data[3] >> 4));
  const std::uint16_t low_raw = static_cast<std::uint16_t>(((data[6] & 0x0f) << 8) | data[5]);
  feedback.high_temperature = static_cast<double>(signExtend12(high_raw)) / 10.0;
  feedback.low_temperature = static_cast<double>(signExtend12(low_raw)) / 10.0;
  return feedback;
}

std::optional<DriveMcuEcodeFeedback> decodeDriveMcuEcodeFeedback(const FrameData & data)
{
  if (!hasValidChecksum(data)) {
    return std::nullopt;
  }
  DriveMcuEcodeFeedback feedback;
  feedback.ecode = toInt32(data[0], data[1], data[2], data[3]);
  return feedback;
}

std::optional<VehDiagFeedback> decodeVehDiagFeedback(const FrameData & data)
{
  if (!hasValidChecksum(data)) {
    return std::nullopt;
  }
  VehDiagFeedback feedback;
  feedback.fault_level = data[0] & 0x0f;
  feedback.auto_can_ctrl_cmd = (data[0] & 0x10) != 0;
  feedback.auto_io_can_cmd = (data[0] & 0x20) != 0;
  feedback.eps_dis_on_line = (data[1] & 0x01) != 0;
  feedback.eps_fault = (data[1] & 0x02) != 0;
  feedback.eps_mosfet_ot = (data[1] & 0x04) != 0;
  feedback.eps_warning = (data[1] & 0x08) != 0;
  feedback.eps_dis_work = (data[1] & 0x10) != 0;
  feedback.eps_over_current = (data[1] & 0x20) != 0;
  feedback.ehb_ecu_fault = (data[2] & 0x10) != 0;
  feedback.ehb_dis_on_line = (data[2] & 0x20) != 0;
  feedback.ehb_work_model_fault = (data[2] & 0x40) != 0;
  feedback.ehb_dis_en = (data[2] & 0x80) != 0;
  feedback.ehb_anguler_fault = (data[3] & 0x01) != 0;
  feedback.ehb_ot = (data[3] & 0x02) != 0;
  feedback.ehb_power_fault = (data[3] & 0x04) != 0;
  feedback.ehb_sensor_abnormal = (data[3] & 0x08) != 0;
  feedback.ehb_motor_fault = (data[3] & 0x10) != 0;
  feedback.ehb_oil_press_sensor_fault = (data[3] & 0x20) != 0;
  feedback.ehb_oil_fault = (data[3] & 0x40) != 0;
  feedback.left_drive_mcu_fault = data[4] & 0x3f;
  // 右驱动 MCU 故障位横跨 data[4] 高 2 位和 data[5] 低 4 位。
  feedback.right_drive_mcu_fault =
    static_cast<std::uint8_t>(((data[5] & 0x0f) << 2) | (data[4] >> 6));
  feedback.aux_bms_dis_on_line = (data[5] & 0x10) != 0;
  feedback.aux_scram = (data[5] & 0x20) != 0;
  feedback.aux_remote_close = (data[5] & 0x40) != 0;
  feedback.aux_remote_dis_on_line = (data[5] & 0x80) != 0;
  return feedback;
}

std::optional<OdoFeedback> decodeOdoFeedback(const FrameData & data)
{
  OdoFeedback feedback;
  // ODO 反馈没有 BCC 字节，8 字节全部用于两个 int32：累计里程(mm)和累计角度(mrad)。
  feedback.accumulative_mileage_m =
    static_cast<double>(toInt32(data[0], data[1], data[2], data[3])) / 1000.0;
  feedback.accumulative_angular_rad =
    static_cast<double>(toInt32(data[4], data[5], data[6], data[7])) / 1000.0;
  return feedback;
}

std::array<std::uint16_t, 4> decodeUltrasonicGroup(const FrameData & data)
{
  // 每个超声距离是 12-bit，无校验字节；一个 CAN 帧打包 4 个距离。
  return {
    static_cast<std::uint16_t>(((data[1] & 0x0f) << 8) | data[0]),
    static_cast<std::uint16_t>((data[2] << 4) | ((data[1] & 0xf0) >> 4)),
    static_cast<std::uint16_t>(((data[4] & 0x0f) << 8) | data[3]),
    static_cast<std::uint16_t>((data[5] << 4) | ((data[4] & 0xf0) >> 4)),
  };
}

}  // namespace yhs::mk_mini
