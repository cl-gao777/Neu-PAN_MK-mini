#include "yhs_can_control/socketcan_helpers.hpp"

#include <linux/can.h>

#include <gtest/gtest.h>

#include "yhs_can_control/mk_mini_protocol.hpp"

namespace
{

TEST(SocketCanHelpers, MarksProtocolIdsAsExtendedFrames)
{
  const canid_t socketcan_id = yhs::socketcan::make_extended_can_id(yhs::mk_mini::kCtrlCmdId);

  EXPECT_NE(socketcan_id & CAN_EFF_FLAG, 0U);
  EXPECT_EQ(socketcan_id & CAN_EFF_MASK, yhs::mk_mini::kCtrlCmdId & CAN_EFF_MASK);
  EXPECT_EQ(socketcan_id, static_cast<canid_t>(0x98C4D2D0));
}

TEST(SocketCanHelpers, NormalizesReceivedExtendedFrameIds)
{
  const canid_t socketcan_id =
    yhs::socketcan::make_extended_can_id(yhs::mk_mini::kVehDiagFbId);

  EXPECT_EQ(yhs::socketcan::normalize_received_can_id(socketcan_id), yhs::mk_mini::kVehDiagFbId);
  EXPECT_EQ(yhs::socketcan::normalize_received_can_id(0x98C4EAEF), yhs::mk_mini::kVehDiagFbId);
}

}  // namespace
