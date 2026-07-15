#include "yhs_can_control/ackermann_odom.hpp"

#include <gtest/gtest.h>

#include <cmath>

namespace
{

using yhs::mk_mini::odom::Pose2D;
using yhs::mk_mini::odom::integrate_ackermann;

constexpr double kPi = 3.14159265358979323846;

TEST(AckermannOdom, KeepsStraightMotionOnCurrentHeading)
{
  const Pose2D start{1.0, 2.0, kPi / 2.0};

  const auto result = integrate_ackermann(start, 1.0, 0.0, 0.6);

  EXPECT_NEAR(result.x, 1.0, 1e-9);
  EXPECT_NEAR(result.y, 3.0, 1e-9);
  EXPECT_NEAR(result.yaw, kPi / 2.0, 1e-9);
}

TEST(AckermannOdom, IntegratesLeftArcFromMileageAndSteering)
{
  const double wheel_base = 0.6;
  const double radius = 2.0;
  const double steering_rad = std::atan(wheel_base / radius);
  const Pose2D start{};

  const auto result = integrate_ackermann(start, 1.0, steering_rad, wheel_base);

  const double expected_yaw = 1.0 / radius;
  EXPECT_NEAR(result.x, radius * std::sin(expected_yaw), 1e-9);
  EXPECT_NEAR(result.y, radius * (1.0 - std::cos(expected_yaw)), 1e-9);
  EXPECT_NEAR(result.yaw, expected_yaw, 1e-9);
}

TEST(AckermannOdom, IntegratesRightArcWithNegativeYaw)
{
  const double wheel_base = 0.6;
  const double radius = 2.0;
  const double steering_rad = -std::atan(wheel_base / radius);
  const Pose2D start{};

  const auto result = integrate_ackermann(start, 1.0, steering_rad, wheel_base);

  EXPECT_GT(result.x, 0.0);
  EXPECT_LT(result.y, 0.0);
  EXPECT_NEAR(result.yaw, -0.5, 1e-9);
}

}  // namespace
