#!/usr/bin/env bash
# docker/scripts/run_odom_test.sh
# Run the MK-mini odometry accuracy test inside the Docker container.
#
# Usage:
#   bash run_odom_test.sh --distance 1.0 --speed 0.5
#   bash run_odom_test.sh --distance 2.0 --speed 0.6 --csv /workspaces/MK-mini_ws/odom_test.csv
#
# This wraps odom_distance_test_node from yhs_can_control.
# The yhs_can_control launch must already be running in another terminal.

set -euo pipefail
export AMENT_TRACE_SETUP_FILES="${AMENT_TRACE_SETUP_FILES:-}"

safe_source() {
  set +u
  source "$1"
  set -u
}


ROS_SETUP="/opt/ros/jazzy/setup.bash"
CHASSIS_INSTALL="/workspaces/MK-mini_ws/ROS2_MK-mini/install/setup.bash"

TARGET_DISTANCE="1.0"
TARGET_SPEED="0.5"
CSV_PATH="/tmp/mkmini_odom_test.csv"
ARMED="true"

usage() {
    cat <<EOF
Usage: bash run_odom_test.sh [OPTIONS]

Options:
  --distance N    Target distance in meters (default: 1.0)
  --speed N       Target speed in m/s (default: 0.5; maximum: 0.6)
  --csv PATH      CSV log output path (default: /tmp/mkmini_odom_test.csv)
  --dry-run       Print the command without executing (armed=false)

Examples:
  bash run_odom_test.sh --distance 0.5 --speed 0.5
  bash run_odom_test.sh --distance 2.0 --speed 0.6 --csv /workspaces/MK-mini_ws/odom_results.csv
  bash run_odom_test.sh --dry-run
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --distance) TARGET_DISTANCE="$2"; shift 2 ;;
        --speed)    TARGET_SPEED="$2"; shift 2 ;;
        --csv)      CSV_PATH="$2"; shift 2 ;;
        --dry-run)  ARMED="false"; shift ;;
        --help|-h)  usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

if [[ ! -f "${ROS_SETUP}" ]]; then
    echo "ERROR: ROS 2 Jazzy not found. Are you inside the container?" >&2
    exit 1
fi

if [[ ! -f "${CHASSIS_INSTALL}" ]]; then
    echo "ERROR: Chassis SDK not built at ${CHASSIS_INSTALL}" >&2
    echo "Build it first:" >&2
    echo "  bash docker/scripts/build_chassis_sdk.sh" >&2
    exit 1
fi

safe_source "${ROS_SETUP}"
safe_source "${CHASSIS_INSTALL}"

echo "=== Odometry Accuracy Test ==="
echo "  Target distance: ${TARGET_DISTANCE} m"
echo "  Target speed:    ${TARGET_SPEED} m/s"
echo "  CSV log:         ${CSV_PATH}"
echo "  Armed:           ${ARMED}"
echo ""

ros2 run yhs_can_control odom_distance_test_node --ros-args \
    -p "armed:=${ARMED}" \
    -p "target_distance_m:=${TARGET_DISTANCE}" \
    -p "target_speed_mps:=${TARGET_SPEED}" \
    -p "log_csv_path:=${CSV_PATH}"

EXIT_CODE=$?
if [[ ${EXIT_CODE} -eq 0 ]] && [[ "${ARMED}" == "true" ]]; then
    echo ""
    echo "Test complete. CSV written to: ${CSV_PATH}"
fi
exit ${EXIT_CODE}
