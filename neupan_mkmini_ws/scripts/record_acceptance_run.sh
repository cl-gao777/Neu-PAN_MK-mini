#!/usr/bin/env bash
set -euo pipefail

run_name="${1:-}"
if [[ -z "$run_name" ]]; then
  echo "Usage: $0 <run-name>" >&2
  exit 1
fi

mkdir -p bags results
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
bag_path="bags/${timestamp}_${run_name}"
result_path="results/${timestamp}_${run_name}.csv"

echo "timestamp_utc,run_name,test_type,success,contact,min_clearance_m,goal_error_m,notes" \
  > "$result_path"
echo "${timestamp},${run_name},FILL_ME,FILL_ME,FILL_ME,FILL_ME,FILL_ME,FILL_ME" \
  >> "$result_path"

exec ros2 bag record -o "$bag_path" \
  /tf /tf_static /scan /map /Odometry /odom /plan \
  /neupan_cmd_vel /neupan/ackermann_cmd /neupan/safety_status \
  /ctrl_cmd /chassis_info_fb /veh_diag_fb
