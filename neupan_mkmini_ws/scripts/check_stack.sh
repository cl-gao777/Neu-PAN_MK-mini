#!/usr/bin/env bash
set -euo pipefail

required_topics=(
  /livox/lidar
  /livox/points
  /odom
  /scan
  /map
  /plan
  /neupan_cmd_vel
  /neupan/ackermann_cmd
  /chassis_info_fb
  /ctrl_cmd
)

topics="$(ros2 topic list)"
failed=0
for topic in "${required_topics[@]}"; do
  if grep -Fxq "$topic" <<<"$topics"; then
    printf "OK      %s\n" "$topic"
  else
    printf "MISSING %s\n" "$topic"
    failed=1
  fi
done

echo
ros2 run tf2_ros tf2_echo map base_link --once || failed=1
echo

nodes="$(ros2 node list)"
if grep -Eq '(^|/)cmd_vel_to_ctrl_cmd_node$' <<<"$nodes"; then
  printf "FORBID  cmd_vel_to_ctrl_cmd_node is running; stop the vendor cmd_vel adapter during NeuPAN control.\n"
  failed=1
else
  printf "OK      cmd_vel_to_ctrl_cmd_node is not running\n"
fi

ctrl_info="$(ros2 topic info /ctrl_cmd || true)"
if grep -Fq "Publisher count: 1" <<<"$ctrl_info"; then
  printf "OK      /ctrl_cmd has exactly one publisher\n"
else
  printf "BAD     /ctrl_cmd must have exactly one publisher\n%s\n" "$ctrl_info"
  failed=1
fi

check_topic_hz() {
  local topic="$1"
  local output
  if ! output="$(timeout 6s ros2 topic hz "$topic" --window 50 2>&1)"; then
    printf "BAD     %s frequency probe failed\n%s\n" "$topic" "$output"
    failed=1
    return
  fi
  if awk '/average rate:/ {rate=$3} END {exit !(rate >= 10.0)}' <<<"$output"; then
    printf "OK      %s >= 10 Hz\n" "$topic"
  else
    printf "BAD     %s must publish at >= 10 Hz\n%s\n" "$topic" "$output"
    failed=1
  fi
}

check_topic_hz /neupan_cmd_vel
check_topic_hz /neupan/ackermann_cmd

exit "$failed"
