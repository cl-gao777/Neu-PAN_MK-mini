#ifndef YHS_CAN_CONTROL__ODOM_DISTANCE_TEST_LOGIC_HPP_
#define YHS_CAN_CONTROL__ODOM_DISTANCE_TEST_LOGIC_HPP_

#include <algorithm>
#include <cmath>
#include <optional>
#include <string>

namespace yhs::mk_mini::odom_test
{

// 里程计测试结束原因，用于终端打印和 CSV 记录。
enum class EndReason
{
  kNone,
  kNotArmed,
  kWaitingForOdom,
  kTargetReached,
  kTimedOut
};

struct Config
{
  // armed 是安全开关；默认 false，防止误启动时车辆运动。
  bool armed{false};
  double target_distance_m{1.0};
  double target_speed_mps{0.05};
  double max_runtime_sec{60.0};
  double distance_tolerance_m{0.01};
};

struct OdomSample
{
  double x{0.0};
  double y{0.0};
};

struct UpdateResult
{
  double command_velocity_mps{0.0};
  double odom_distance_m{0.0};
  double runtime_sec{0.0};
  bool terminal{false};
  bool started_now{false};
  EndReason reason{EndReason::kNone};
};

inline const char * to_string(const EndReason reason)
{
  switch (reason) {
    case EndReason::kNone:
      return "running";
    case EndReason::kNotArmed:
      return "not_armed";
    case EndReason::kWaitingForOdom:
      return "waiting_for_odom";
    case EndReason::kTargetReached:
      return "target_reached";
    case EndReason::kTimedOut:
      return "timed_out";
  }
  return "unknown";
}

class DistanceTestController
{
public:
  // 输入当前参数、最新 /odom 样本和当前时间，输出本周期应该发布的速度和状态。
  UpdateResult update(
    const Config & config,
    const std::optional<OdomSample> & odom_sample,
    const double now_sec)
  {
    if (finished_) {
      return make_terminal_result();
    }

    if (!config.armed) {
      // 未解锁时绝不输出非零速度。
      return UpdateResult{0.0, 0.0, 0.0, false, false, EndReason::kNotArmed};
    }

    if (!odom_sample.has_value()) {
      // 没有 /odom 就无法判断走了多远，因此保持停车。
      return UpdateResult{0.0, 0.0, 0.0, false, false, EndReason::kWaitingForOdom};
    }

    bool started_now = false;
    if (!started_) {
      // 第一次收到 /odom 时记录起点，后续距离都相对这个点计算。
      start_ = odom_sample.value();
      start_time_sec_ = now_sec;
      started_ = true;
      started_now = true;
    }

    const double distance = distance_from_start(odom_sample.value());
    const double runtime = std::max(0.0, now_sec - start_time_sec_);

    if (distance + config.distance_tolerance_m >= config.target_distance_m) {
      // tolerance 允许提前一点点停车，避免因为离散采样刚好越过目标距离太多。
      finish(EndReason::kTargetReached, distance, runtime, now_sec);
      UpdateResult result = make_terminal_result();
      result.started_now = started_now;
      return result;
    }

    if (runtime >= config.max_runtime_sec) {
      finish(EndReason::kTimedOut, distance, runtime, now_sec);
      UpdateResult result = make_terminal_result();
      result.started_now = started_now;
      return result;
    }

    return UpdateResult{
      config.target_speed_mps,
      distance,
      runtime,
      false,
      started_now,
      EndReason::kNone};
  }

  bool started() const
  {
    return started_;
  }

  bool finished() const
  {
    return finished_;
  }

  double finish_time_sec() const
  {
    return finish_time_sec_;
  }

  EndReason finish_reason() const
  {
    return finish_reason_;
  }

  double final_distance_m() const
  {
    return final_distance_m_;
  }

  double final_runtime_sec() const
  {
    return final_runtime_sec_;
  }

private:
  double distance_from_start(const OdomSample & sample) const
  {
    return std::hypot(sample.x - start_.x, sample.y - start_.y);
  }

  void finish(
    const EndReason reason,
    const double distance,
    const double runtime,
    const double now_sec)
  {
    finished_ = true;
    finish_reason_ = reason;
    final_distance_m_ = distance;
    final_runtime_sec_ = runtime;
    finish_time_sec_ = now_sec;
  }

  UpdateResult make_terminal_result() const
  {
    return UpdateResult{
      0.0,
      final_distance_m_,
      final_runtime_sec_,
      true,
      false,
      finish_reason_ == EndReason::kNone ? EndReason::kTargetReached : finish_reason_};
  }

  bool started_{false};
  bool finished_{false};
  OdomSample start_;
  double start_time_sec_{0.0};
  double finish_time_sec_{0.0};
  EndReason finish_reason_{EndReason::kNone};
  double final_distance_m_{0.0};
  double final_runtime_sec_{0.0};
};

}  // namespace yhs::mk_mini::odom_test

#endif  // YHS_CAN_CONTROL__ODOM_DISTANCE_TEST_LOGIC_HPP_
