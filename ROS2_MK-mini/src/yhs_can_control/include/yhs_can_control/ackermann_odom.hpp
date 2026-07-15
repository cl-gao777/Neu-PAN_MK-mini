#ifndef YHS_CAN_CONTROL__ACKERMANN_ODOM_HPP_
#define YHS_CAN_CONTROL__ACKERMANN_ODOM_HPP_

#include <cmath>

namespace yhs::mk_mini::odom
{

struct Pose2D
{
  double x{0.0};
  double y{0.0};
  double yaw{0.0};
};

inline Pose2D integrate_ackermann(
  const Pose2D & start,
  const double delta_distance_m,
  const double steering_rad,
  const double wheel_base_m)
{
  Pose2D result = start;
  const double curvature = std::tan(steering_rad) / wheel_base_m;

  if (std::abs(curvature) < 1e-12) {
    result.x += delta_distance_m * std::cos(start.yaw);
    result.y += delta_distance_m * std::sin(start.yaw);
    return result;
  }

  const double delta_yaw = delta_distance_m * curvature;
  const double end_yaw = start.yaw + delta_yaw;
  const double radius = 1.0 / curvature;
  result.x += radius * (std::sin(end_yaw) - std::sin(start.yaw));
  result.y -= radius * (std::cos(end_yaw) - std::cos(start.yaw));
  result.yaw = end_yaw;
  return result;
}

}  // namespace yhs::mk_mini::odom

#endif  // YHS_CAN_CONTROL__ACKERMANN_ODOM_HPP_
