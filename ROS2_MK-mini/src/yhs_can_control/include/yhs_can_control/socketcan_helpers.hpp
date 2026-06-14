#ifndef YHS_CAN_CONTROL_SOCKETCAN_HELPERS_HPP_
#define YHS_CAN_CONTROL_SOCKETCAN_HELPERS_HPP_

#include <linux/can.h>

#include <cstdint>

namespace yhs::socketcan
{

inline canid_t make_extended_can_id(const std::uint32_t protocol_id)
{
  return static_cast<canid_t>((protocol_id & CAN_EFF_MASK) | CAN_EFF_FLAG);
}

inline std::uint32_t normalize_received_can_id(const canid_t socketcan_id)
{
  return static_cast<std::uint32_t>(socketcan_id & CAN_EFF_MASK);
}

}  // namespace yhs::socketcan

#endif  // YHS_CAN_CONTROL_SOCKETCAN_HELPERS_HPP_
