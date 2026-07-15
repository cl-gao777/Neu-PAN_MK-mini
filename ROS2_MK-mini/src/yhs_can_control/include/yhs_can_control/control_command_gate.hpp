#ifndef YHS_CAN_CONTROL_CONTROL_COMMAND_GATE_HPP_
#define YHS_CAN_CONTROL_CONTROL_COMMAND_GATE_HPP_

#include <cstdint>

#include "yhs_can_control/mk_mini_protocol.hpp"

namespace yhs
{

struct ControlCommandGateConfig
{
  double max_velocity_mps{0.6};
  double max_steering_deg{25.0};
  double command_timeout_sec{0.3};
  double send_rate_hz{50.0};
  bool allow_reverse{false};
  std::uint8_t forward_gear{4};
  std::uint8_t reverse_gear{2};
};

class ControlCommandGate
{
public:
  explicit ControlCommandGate(ControlCommandGateConfig config = {});

  void update(const mk_mini::CtrlCommand & command, double now_sec);
  mk_mini::CtrlCommand command_for_send(double now_sec);

private:
  static mk_mini::CtrlCommand stop_command();
  void invalidate();
  bool observe_time(double now_sec);

  ControlCommandGateConfig config_;
  mk_mini::CtrlCommand command_{stop_command()};
  double command_time_sec_{0.0};
  double last_observed_time_sec_{0.0};
  bool have_command_{false};
  bool have_observed_time_{false};
};

}  // namespace yhs

#endif  // YHS_CAN_CONTROL_CONTROL_COMMAND_GATE_HPP_
