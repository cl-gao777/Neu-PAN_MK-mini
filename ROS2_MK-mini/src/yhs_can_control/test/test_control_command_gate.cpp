#include <gtest/gtest.h>

#include <cmath>
#include <limits>

#if __has_include("yhs_can_control/control_command_gate.hpp")
#include "yhs_can_control/control_command_gate.hpp"

namespace yhs
{
namespace
{

using mk_mini::CtrlCommand;

void expect_stop(const CtrlCommand & command)
{
  EXPECT_EQ(command.gear, 4);
  EXPECT_DOUBLE_EQ(command.velocity_mps, 0.0);
  EXPECT_DOUBLE_EQ(command.steering_deg, 0.0);
}

TEST(ControlCommandGateTest, UsesConservativeDefaults)
{
  const ControlCommandGateConfig config;

  EXPECT_DOUBLE_EQ(config.max_velocity_mps, 0.6);
  EXPECT_DOUBLE_EQ(config.max_steering_deg, 25.0);
  EXPECT_DOUBLE_EQ(config.command_timeout_sec, 0.3);
  EXPECT_DOUBLE_EQ(config.send_rate_hz, 50.0);
  EXPECT_FALSE(config.allow_reverse);
  EXPECT_EQ(config.forward_gear, 4);
  EXPECT_EQ(config.reverse_gear, 2);
}

TEST(ControlCommandGateTest, StopsBeforeReceivingACommand)
{
  ControlCommandGate gate;

  expect_stop(gate.command_for_send(10.0));
}

TEST(ControlCommandGateTest, RejectsNonFiniteAndNegativeMotionValues)
{
  ControlCommandGate gate;
  const double nan = std::numeric_limits<double>::quiet_NaN();
  const double inf = std::numeric_limits<double>::infinity();

  for (const auto & command : {
        CtrlCommand{4, nan, 0.0, 0},
        CtrlCommand{4, inf, 0.0, 0},
        CtrlCommand{4, 0.2, nan, 0},
        CtrlCommand{4, 0.2, -inf, 0},
        CtrlCommand{4, -0.1, 0.0, 0}})
  {
    gate.update(command, 1.0);
    expect_stop(gate.command_for_send(1.0));
  }
}

TEST(ControlCommandGateTest, EnforcesOfficialGearRules)
{
  ControlCommandGate gate;

  for (const auto gear : {0, 1, 3}) {
    gate.update(CtrlCommand{static_cast<std::uint8_t>(gear), 0.1, 2.0, 0}, 1.0);
    expect_stop(gate.command_for_send(1.0));
  }

  gate.update(CtrlCommand{5, 0.1, 2.0, 0}, 2.0);
  expect_stop(gate.command_for_send(2.0));

  gate.update(CtrlCommand{2, 0.1, 2.0, 0}, 3.0);
  expect_stop(gate.command_for_send(3.0));

  for (const auto gear : {0, 1, 3}) {
    gate.update(CtrlCommand{static_cast<std::uint8_t>(gear), 0.0, 2.0, 0}, 4.0);
    const auto output = gate.command_for_send(4.0);
    EXPECT_EQ(output.gear, gear);
    EXPECT_DOUBLE_EQ(output.velocity_mps, 0.0);
    EXPECT_DOUBLE_EQ(output.steering_deg, 0.0);
  }
}

TEST(ControlCommandGateTest, AllowsConfiguredReverseAndClampsValidMotion)
{
  ControlCommandGateConfig config;
  config.allow_reverse = true;
  ControlCommandGate gate(config);

  gate.update(CtrlCommand{4, 1.2, 40.0, 0}, 10.0);
  const auto forward = gate.command_for_send(10.0);
  EXPECT_EQ(forward.gear, 4);
  EXPECT_DOUBLE_EQ(forward.velocity_mps, 0.6);
  EXPECT_DOUBLE_EQ(forward.steering_deg, 25.0);

  gate.update(CtrlCommand{2, 0.8, -40.0, 0}, 11.0);
  const auto reverse = gate.command_for_send(11.0);
  EXPECT_EQ(reverse.gear, 2);
  EXPECT_DOUBLE_EQ(reverse.velocity_mps, 0.6);
  EXPECT_DOUBLE_EQ(reverse.steering_deg, -25.0);
}

TEST(ControlCommandGateTest, StopsAfterTimeoutButNotAtBoundary)
{
  ControlCommandGate gate;
  gate.update(CtrlCommand{4, 0.2, 5.0, 0}, 0.0);

  EXPECT_DOUBLE_EQ(gate.command_for_send(0.3).velocity_mps, 0.2);
  expect_stop(gate.command_for_send(0.300001));
}

TEST(ControlCommandGateTest, StopsAtTheFirstRepresentableTimeAfterTimeout)
{
  ControlCommandGateConfig config;
  ControlCommandGate gate(config);
  gate.update(CtrlCommand{4, 0.2, 5.0, 0}, 0.0);

  EXPECT_DOUBLE_EQ(
    gate.command_for_send(config.command_timeout_sec).velocity_mps, 0.2);
  const double just_expired = std::nextafter(
    config.command_timeout_sec, std::numeric_limits<double>::infinity());
  expect_stop(gate.command_for_send(just_expired));
}

TEST(ControlCommandGateTest, StopsForNonFiniteOrBackwardTimeAndRecoversOnFreshUpdate)
{
  ControlCommandGate gate;
  const double nan = std::numeric_limits<double>::quiet_NaN();
  gate.update(CtrlCommand{4, 0.2, 5.0, 0}, 10.0);

  expect_stop(gate.command_for_send(nan));
  gate.update(CtrlCommand{4, 0.3, 6.0, 0}, 11.0);
  EXPECT_DOUBLE_EQ(gate.command_for_send(11.0).velocity_mps, 0.3);

  expect_stop(gate.command_for_send(10.5));
  gate.update(CtrlCommand{4, 0.4, 7.0, 0}, 12.0);
  EXPECT_DOUBLE_EQ(gate.command_for_send(12.0).velocity_mps, 0.4);
}

TEST(ControlCommandGateTest, InvalidUpdateReplacesPriorMotionWithStopAndValidUpdateRecovers)
{
  ControlCommandGate gate;
  gate.update(CtrlCommand{4, 0.2, 5.0, 0}, 1.0);
  EXPECT_DOUBLE_EQ(gate.command_for_send(1.0).velocity_mps, 0.2);

  gate.update(CtrlCommand{9, 0.2, 5.0, 0}, 1.1);
  expect_stop(gate.command_for_send(1.1));

  gate.update(CtrlCommand{4, 0.5, -3.0, 0}, 1.2);
  const auto recovered = gate.command_for_send(1.2);
  EXPECT_DOUBLE_EQ(recovered.velocity_mps, 0.5);
  EXPECT_DOUBLE_EQ(recovered.steering_deg, -3.0);
}

TEST(ControlCommandGateTest, EvaluationRollbackResetsBaselineForImmediateRecovery)
{
  ControlCommandGate gate;
  gate.update(CtrlCommand{4, 0.2, 5.0, 0}, 10.0);

  expect_stop(gate.command_for_send(2.0));
  gate.update(CtrlCommand{4, 0.3, 6.0, 0}, 2.1);

  EXPECT_DOUBLE_EQ(gate.command_for_send(2.1).velocity_mps, 0.3);
}

TEST(ControlCommandGateTest, UpdateRollbackIsRejectedAndResetsBaselineForRecovery)
{
  ControlCommandGate gate;
  gate.update(CtrlCommand{4, 0.2, 5.0, 0}, 10.0);

  gate.update(CtrlCommand{4, 0.3, 6.0, 0}, 2.0);
  expect_stop(gate.command_for_send(2.0));

  gate.update(CtrlCommand{4, 0.4, 7.0, 0}, 2.1);
  EXPECT_DOUBLE_EQ(gate.command_for_send(2.1).velocity_mps, 0.4);
}

}  // namespace
}  // namespace yhs

#else

TEST(ControlCommandGateTest, SafetyGateImplementationIsRequired)
{
  FAIL() << "control_command_gate.hpp is missing";
}

#endif
