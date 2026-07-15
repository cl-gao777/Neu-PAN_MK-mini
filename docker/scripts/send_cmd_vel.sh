#!/usr/bin/env bash
# docker/scripts/send_cmd_vel.sh
# Convenience wrapper for publishing Twist messages to /cmd_vel.
# Run inside the Docker container while yhs_can_control is launched.
#
# Usage:
#   bash send_cmd_vel.sh forward [speed]      # default 0.5 m/s
#   bash send_cmd_vel.sh turn [speed] [angle] # default 0.5 m/s, 0.1 rad
#   bash send_cmd_vel.sh stop
#
# WARNING: First-time motion tests should be done with wheels lifted
#          or in a controlled test area.

set -euo pipefail
export AMENT_TRACE_SETUP_FILES="${AMENT_TRACE_SETUP_FILES:-}"

safe_source() {
  set +u
  source "$1"
  set -u
}


ROS_SETUP="/opt/ros/jazzy/setup.bash"
CHASSIS_INSTALL="/workspaces/MK-mini_ws/ROS2_MK-mini/install/setup.bash"

usage() {
    cat <<EOF
Usage: bash send_cmd_vel.sh COMMAND [args]

Commands:
  forward [speed]        Move forward at speed m/s (default: 0.5)
  turn [speed] [angle]   Turn while moving (default: 0.5 m/s, 0.1 rad)
  stop                   Stop immediately (zero velocity)
  reverse [speed]        Rejected: real-robot testing is forward-only

Examples:
  bash send_cmd_vel.sh forward
  bash send_cmd_vel.sh forward 0.5
  bash send_cmd_vel.sh turn 0.5 0.2
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
safe_source "${ROS_SETUP}"
if [[ -f "${CHASSIS_INSTALL}" ]]; then
    safe_source "${CHASSIS_INSTALL}"
fi

case "${COMMAND}" in
    forward)
        SPEED="${1:-0.5}"
        echo "Publishing: forward at ${SPEED} m/s"
        ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
            "{linear: {x: ${SPEED}}, angular: {z: 0.0}}"
        ;;
    turn)
        SPEED="${1:-0.5}"
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
        echo "ERROR: reverse commands are disabled for MK-mini real-robot testing." >&2
        exit 2
        ;;
    *)
        echo "ERROR: Unknown command '${COMMAND}'" >&2
        usage
        ;;
esac
