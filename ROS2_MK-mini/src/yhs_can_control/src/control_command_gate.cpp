#include "yhs_can_control/control_command_gate.hpp"

#include <algorithm>
#include <cmath>

namespace yhs
{
namespace
{

constexpr std::uint8_t kDisableGear = 0;
constexpr std::uint8_t kParkGear = 1;
constexpr std::uint8_t kReverseGear = 2;
constexpr std::uint8_t kNeutralGear = 3;
constexpr std::uint8_t kDriveGear = 4;

bool is_non_motion_gear(const std::uint8_t gear)
{
  return gear == kDisableGear || gear == kParkGear || gear == kNeutralGear;
}

}  // namespace

ControlCommandGate::ControlCommandGate(ControlCommandGateConfig config)
: config_(config)
{
}

mk_mini::CtrlCommand ControlCommandGate::stop_command()
{
  mk_mini::CtrlCommand command;
  command.gear = kDriveGear;
  command.velocity_mps = 0.0;
  command.steering_deg = 0.0;
  command.brake = 0;
  return command;
}

void ControlCommandGate::invalidate()
{
  have_command_ = false;
  command_ = stop_command();
}

bool ControlCommandGate::observe_time(const double now_sec)
{
  if (!std::isfinite(now_sec)) {
    invalidate();
    have_observed_time_ = false;
    return false;
  }
  if (have_observed_time_ && now_sec < last_observed_time_sec_) {
    invalidate();
    last_observed_time_sec_ = now_sec;
    return false;
  }
  last_observed_time_sec_ = now_sec;
  have_observed_time_ = true;
  return true;
}

void ControlCommandGate::update(const mk_mini::CtrlCommand & command, const double now_sec)
{
  if (!observe_time(now_sec) || !std::isfinite(command.velocity_mps) ||
    !std::isfinite(command.steering_deg) || command.velocity_mps < 0.0)
  {
    invalidate();
    return;
  }

  const bool legal_gear = command.gear <= kDriveGear;
  const bool drive = command.gear == kDriveGear && command.gear == config_.forward_gear;
  const bool reverse = command.gear == kReverseGear && command.gear == config_.reverse_gear;
  if (!legal_gear || (reverse && !config_.allow_reverse) ||
    (!drive && !reverse && !is_non_motion_gear(command.gear)) ||
    (is_non_motion_gear(command.gear) && command.velocity_mps != 0.0))
  {
    invalidate();
    return;
  }

  command_ = command;
  if (command.velocity_mps == 0.0 || is_non_motion_gear(command.gear)) {
    command_.velocity_mps = 0.0;
    command_.steering_deg = 0.0;
  } else {
    command_.velocity_mps = std::min(command.velocity_mps, config_.max_velocity_mps);
    command_.steering_deg = std::clamp(
      command.steering_deg, -config_.max_steering_deg, config_.max_steering_deg);
  }
  command_time_sec_ = now_sec;
  have_command_ = true;
}

mk_mini::CtrlCommand ControlCommandGate::command_for_send(const double now_sec)
{
  if (!observe_time(now_sec) || !have_command_) {
    return stop_command();
  }

  const double age_sec = now_sec - command_time_sec_;
  if (age_sec > config_.command_timeout_sec) {
    invalidate();
    return stop_command();
  }
  return command_;
}

}  // namespace yhs
