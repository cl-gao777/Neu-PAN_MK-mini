#!/usr/bin/env bash
# docker/scripts/build_chassis_sdk.sh
# Build the MK-mini chassis SDK (yhs_can_interfaces + yhs_can_control)
# inside the Docker container.
#
# Usage: bash build_chassis_sdk.sh

set -euo pipefail

ROS_SETUP="/opt/ros/jazzy/setup.bash"
CHASSIS_WS="/workspaces/MK-mini_ws/ROS2_MK-mini"

if [[ ! -f "${ROS_SETUP}" ]]; then
    echo "ERROR: ROS 2 Jazzy not found at ${ROS_SETUP}. Are you inside the container?" >&2
    exit 1
fi

if [[ ! -d "${CHASSIS_WS}/src" ]]; then
    echo "ERROR: Chassis workspace not found at ${CHASSIS_WS}" >&2
    echo "Ensure the repository is bind-mounted at /workspaces/MK-mini_ws" >&2
    exit 1
fi

echo "=== Building MK-mini Chassis SDK ==="
echo "  Workspace: ${CHASSIS_WS}"
echo ""

source "${ROS_SETUP}"
cd "${CHASSIS_WS}"

# Clean stale build artifacts from a different architecture (e.g. x86_64 -> ARM64)
if [[ -d build || -d install || -d log ]]; then
    echo "Removing stale build/ install/ log/ directories..."
    rm -rf build install log
fi

colcon build --symlink-install \
    --packages-select yhs_can_interfaces yhs_can_control

echo ""
echo "Build complete. Source the workspace with:"
echo "  source ${CHASSIS_WS}/install/setup.bash"
