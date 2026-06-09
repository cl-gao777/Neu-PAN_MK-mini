#include "yhs_can_control/odom_distance_test_logic.hpp"

#include <gtest/gtest.h>

#include <optional>

// 里程计距离测试逻辑的单元测试：只测纯状态机，不依赖 ROS 节点和实车。

namespace
{

using yhs::mk_mini::odom_test::Config;
using yhs::mk_mini::odom_test::DistanceTestController;
using yhs::mk_mini::odom_test::EndReason;
using yhs::mk_mini::odom_test::OdomSample;

TEST(OdomDistanceTestLogic, DoesNotMoveWhenNotArmed)
{
  Config config;
  config.armed = false;
  DistanceTestController controller;

  const auto result = controller.update(config, OdomSample{0.0, 0.0}, 1.0);

  EXPECT_DOUBLE_EQ(result.command_velocity_mps, 0.0);
  EXPECT_FALSE(result.terminal);
  EXPECT_EQ(result.reason, EndReason::kNotArmed);
}

TEST(OdomDistanceTestLogic, WaitsForOdomBeforeMoving)
{
  Config config;
  config.armed = true;
  DistanceTestController controller;

  const auto result = controller.update(config, std::nullopt, 1.0);

  EXPECT_DOUBLE_EQ(result.command_velocity_mps, 0.0);
  EXPECT_FALSE(result.terminal);
  EXPECT_EQ(result.reason, EndReason::kWaitingForOdom);
}

TEST(OdomDistanceTestLogic, CommandsVelocityUntilTargetDistance)
{
  Config config;
  config.armed = true;
  config.target_distance_m = 1.0;
  config.target_speed_mps = 0.05;
  config.distance_tolerance_m = 0.01;
  DistanceTestController controller;

  const auto start = controller.update(config, OdomSample{0.0, 0.0}, 10.0);
  EXPECT_TRUE(start.started_now);
  EXPECT_FALSE(start.terminal);
  EXPECT_DOUBLE_EQ(start.command_velocity_mps, 0.05);

  const auto running = controller.update(config, OdomSample{0.5, 0.0}, 20.0);
  EXPECT_FALSE(running.terminal);
  EXPECT_DOUBLE_EQ(running.command_velocity_mps, 0.05);
  EXPECT_NEAR(running.odom_distance_m, 0.5, 1e-9);

  const auto finished = controller.update(config, OdomSample{0.99, 0.0}, 30.0);
  EXPECT_TRUE(finished.terminal);
  EXPECT_DOUBLE_EQ(finished.command_velocity_mps, 0.0);
  EXPECT_EQ(finished.reason, EndReason::kTargetReached);
  EXPECT_NEAR(finished.odom_distance_m, 0.99, 1e-9);
}

TEST(OdomDistanceTestLogic, StopsOnTimeout)
{
  Config config;
  config.armed = true;
  config.target_distance_m = 2.0;
  config.target_speed_mps = 0.05;
  config.max_runtime_sec = 5.0;
  DistanceTestController controller;

  const auto start = controller.update(config, OdomSample{0.0, 0.0}, 1.0);
  EXPECT_FALSE(start.terminal);

  const auto timed_out = controller.update(config, OdomSample{0.1, 0.0}, 6.0);
  EXPECT_TRUE(timed_out.terminal);
  EXPECT_DOUBLE_EQ(timed_out.command_velocity_mps, 0.0);
  EXPECT_EQ(timed_out.reason, EndReason::kTimedOut);
}

}  // namespace
