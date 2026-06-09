#!/usr/bin/env bash
set -euo pipefail

ros2 topic pub --once /neupan/drive_enable std_msgs/msg/Bool "{data: false}"
ros2 topic pub --once /neupan/emergency_stop std_msgs/msg/Bool "{data: true}"
