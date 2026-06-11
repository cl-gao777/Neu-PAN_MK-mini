#!/usr/bin/env bash
# docker/scripts/send_cmd_vel.sh
# Convenience wrapper for publishing Twist messages to /cmd_vel.
# Run inside the Docker container while yhs_can_control is launched.
#
# Usage:
#   bash send_cmd_vel.sh forward [speed]      # default 0.05 m/s
#   bash send_cmd_vel.sh turn [speed] [angle] # default 0.05 m/s, 0.1 rad
#   bash send_cmd_vel.sh stop
#   bash send_cmd_vel.sh reverse [speed]      # default 0.05 m/s
#
# WARNING: First-time motion tests should be done with wheels lifted
#          or in a controlled test area.

set -euo pipefail

ROS_SETUP="/opt/ros/jazzy/setup.bash"
CHASSIS_INSTALL="/workspaces/MK-mini_ws/ROS2_MK-mini/install/setup.bash"

usage() {
    cat <<EOF
Usage: bash send_cmd_vel.sh COMMAND [args]

Commands:
  forward [speed]        Move forward at speed m/s (default: 0.05)
  turn [speed] [angle]   Turn while moving (default: 0.05 m/s, 0.1 rad)
  stop                   Stop immediately (zero velocity)
  reverse [speed]        Move backward at speed m/s (default: 0.05)
                         NOTE: Chassis default is allow_reverse=false

Examples:
  bash send_cmd_vel.sh forward
  bash send_cmd_vel.sh forward 0.1
  bash send_cmd_vel.sh turn 0.05 0.2
  bash send_cmd_vel.sh stop
EOF
    exit 0
}

if [[ $# -lt 1 ]]; then
    usage
fi

COMMAND="$1"
shift || true

if [[ ! -f "${ROS_SETUP}" ]]; then
    echo "ERROR: ROS 2 Jazzy not found. Are you inside the container?" >&2
    exit 1
fi

# Source ROS 2 unconditionally; source chassis install if it exists
source "${ROS_SETUP}"
if [[ -f "${CHASSIS_INSTALL}" ]]; then
    source "${CHASSIS_INSTALL}"
fi

case "${COMMAND}" in
    forward)
        SPEED="${1:-0.05}"
        echo "Publishing: forward at ${SPEED} m/s"
        ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
            "{linear: {x: ${SPEED}}, angular: {z: 0.0}}"
        ;;
    turn)
        SPEED="${1:-0.05}"
        ANGLE="${2:-0.1}"
        echo "Publishing: forward at ${SPEED} m/s, turn at ${ANGLE} rad/s"
        ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
            "{linear: {x: ${SPEED}}, angular: {z: ${ANGLE}}}"
        ;;
    stop)
        echo "Publishing: stop"
        ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
            "{linear: {x: 0.0}, angular: {z: 0.0}}"
        ;;
    reverse)
        SPEED="${1:-0.05}"
        echo "Publishing: reverse at ${SPEED} m/s"
        echo "WARNING: Chassis default config has allow_reverse=false" >&2
        ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
            "{linear: {x: -${SPEED}}, angular: {z: 0.0}}"
        ;;
    *)
        echo "ERROR: Unknown command '${COMMAND}'" >&2
        usage
        ;;
esac
