#include "yhs_can_control/mk_mini_protocol.hpp"

#include <gtest/gtest.h>

// 协议层单元测试：验证 CAN 编码、校验、温度符号扩展和诊断位解析是否符合厂家 DBC。

namespace
{

using yhs::mk_mini::FrameData;

TEST(MkMiniProtocol, EncodesCtrlCommandWithChecksumAndAliveCounter)
{
  const auto data = yhs::mk_mini::encodeCtrlCommand({1, 1.234, 12.34, 0}, 3);

  EXPECT_EQ(data[0], 0x21);
  EXPECT_EQ(data[1], 0x4d);
  EXPECT_EQ(data[2], 0x20);
  EXPECT_EQ(data[3], 0x4d);
  EXPECT_EQ(data[4] & 0x0f, 0x00);
  EXPECT_EQ(data[6], 0x30);
  EXPECT_EQ(data[7], yhs::mk_mini::checksum(data));
}

TEST(MkMiniProtocol, RejectsBadChecksum)
{
  auto data = yhs::mk_mini::encodeCtrlCommand({1, 0.1, 0.0, 0}, 0);
  data[7] ^= 0xff;

  EXPECT_FALSE(yhs::mk_mini::decodeCtrlFeedback(data).has_value());
}

TEST(MkMiniProtocol, DecodesSignedTwelveBitBmsTemperatures)
{
  FrameData data{};
  // 高温原始值 = -10.0 C / 0.1 = -100 = signed 12-bit 中的 0xf9c。
  // 低温原始值 = -1.0 C / 0.1 = -10 = signed 12-bit 中的 0xff6。
  data[3] = 0xc0;
  data[4] = 0xf9;
  data[5] = 0xf6;
  data[6] = 0x0f;
  data[7] = yhs::mk_mini::checksum(data);

  const auto decoded = yhs::mk_mini::decodeBmsFlagInfoFeedback(data);

  ASSERT_TRUE(decoded.has_value());
  EXPECT_DOUBLE_EQ(decoded->high_temperature, -10.0);
  EXPECT_DOUBLE_EQ(decoded->low_temperature, -1.0);
}

TEST(MkMiniProtocol, DecodesRightDriveMcuFaultBits)
{
  FrameData data{};
  data[4] = 0x80;
  data[5] = 0x0a;
  data[7] = yhs::mk_mini::checksum(data);

  const auto decoded = yhs::mk_mini::decodeVehDiagFeedback(data);

  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->left_drive_mcu_fault, 0x00);
  EXPECT_EQ(decoded->right_drive_mcu_fault, 0x2a);
}

}  // namespace
