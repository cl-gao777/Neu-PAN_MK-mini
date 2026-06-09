#!/usr/bin/env bash
set -euo pipefail

required_topics=(
  /livox/lidar
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
timeout 6s ros2 topic hz /neupan_cmd_vel --window 50 || true

exit "$failed"
