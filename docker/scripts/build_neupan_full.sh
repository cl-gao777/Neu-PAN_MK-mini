#!/usr/bin/env bash
# docker/scripts/build_neupan_full.sh
# Build the complete NeuPAN integration workspace inside the Docker container.
# Requires one-time initialization first (vcs import + chassis package copy).
#
# Usage: bash build_neupan_full.sh

set -euo pipefail
export AMENT_TRACE_SETUP_FILES="${AMENT_TRACE_SETUP_FILES:-}"

safe_source() {
  set +u
  source "$1"
  set -u
}


ROS_SETUP="/opt/ros/jazzy/setup.bash"
NEUPAN_WS="/workspaces/MK-mini_ws/neupan_mkmini_ws"
CHASSIS_SRC="/workspaces/MK-mini_ws/ROS2_MK-mini/src"

if [[ ! -f "${ROS_SETUP}" ]]; then
    echo "ERROR: ROS 2 Jazzy not found. Are you inside the container?" >&2
    exit 1
fi

if [[ ! -d "${NEUPAN_WS}" ]]; then
    echo "ERROR: NeuPAN workspace not found at ${NEUPAN_WS}" >&2
    exit 1
fi

safe_source "${ROS_SETUP}"
cd "${NEUPAN_WS}"

# ---- Pre-flight: one-time initialization checks ----
MISSING=0

if [[ ! -d src/neupan_ros2 || ! -d src/livox_ros_driver2 || ! -d src/FAST_LIO ]]; then
    echo "--- External repos not yet imported ---"
    echo "Run once (inside container):"
    echo "  cd ${NEUPAN_WS}"
    echo "  safe_source "/opt/ros/jazzy/setup.bash""
    echo "  vcs import . < mkmini_neupan.repos"
    echo ""
    MISSING=1
fi

if [[ ! -d src/yhs_can_control || ! -d src/yhs_can_interfaces ]]; then
    echo "--- Chassis packages not yet copied ---"
    echo "Run once (inside container):"
    echo "  cp -a ${CHASSIS_SRC}/yhs_can_control ${NEUPAN_WS}/src/"
    echo "  cp -a ${CHASSIS_SRC}/yhs_can_interfaces ${NEUPAN_WS}/src/"
    echo ""
    MISSING=1
fi

if [[ ${MISSING} -eq 1 ]]; then
    echo "Complete the initialization steps above, then re-run this script." >&2
    exit 1
fi

# ---- Bootstrap ----
echo "=== Building NeuPAN Full Stack ==="
echo "  Workspace: ${NEUPAN_WS}"
echo ""

bash scripts/bootstrap_jazzy.sh
