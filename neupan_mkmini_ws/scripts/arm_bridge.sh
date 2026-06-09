#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "I_HAVE_REMOTE_AND_ESTOP" ]]; then
  echo "Refusing to arm. Confirm wheels-up checks, remote takeover, and E-stop." >&2
  echo "Usage: $0 I_HAVE_REMOTE_AND_ESTOP" >&2
  exit 1
fi

ros2 topic pub --once /neupan/emergency_stop std_msgs/msg/Bool "{data: false}"
ros2 topic pub --once /neupan/drive_enable std_msgs/msg/Bool "{data: true}"
