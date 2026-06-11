#!/usr/bin/env bash
# docker/run_mkmini_dev.sh
# Launch an interactive development container for MK-mini NeuPAN on Thor.
#
# Usage: bash run_mkmini_dev.sh
#
# Key design principles:
#   - Image (mkmini-jazzy:dev) contains ONLY the environment.
#   - Source code is bind-mounted from the host at runtime.
#   - Image must be built ON Thor; see README.md for instructions.

set -euo pipefail

IMAGE_NAME="mkmini-jazzy:dev"

# Path to the repository on the Thor host filesystem.
# Update this if you cloned/transferred the repo to a different location.
HOST_WS_DIR="${HOME}/workspaces/MK-mini_ws"

# -------------------------------------------
# Pre-flight checks
# -------------------------------------------

if [[ ! -d "${HOST_WS_DIR}" ]]; then
    echo "ERROR: Host workspace not found at ${HOST_WS_DIR}" >&2
    echo "Transfer the code first:" >&2
    echo "  scp -r E:\\Codex_ws\\MK-mini_ws <user>@<thor_ip>:~/workspaces/" >&2
    echo "Or update HOST_WS_DIR in this script." >&2
    exit 1
fi

if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    echo "ERROR: Docker image '${IMAGE_NAME}' not found." >&2
    echo "Build it first:" >&2
    echo "  cd ~/workspaces/MK-mini_ws/docker" >&2
    echo "  docker build -t ${IMAGE_NAME} ." >&2
    exit 1
fi

# -------------------------------------------
# Launch container
# -------------------------------------------
# Flag rationale:
#   --network host   Required for DDS discovery, Livox UDP, and CAN bus
#   --ipc host       Required for ROS 2 shared-memory transport
#   --pid host       Simplifies debugging (gdb, perf) and signal handling
#   --privileged     Required for SocketCAN /dev access and raw sockets
#   -v (bind mount)  Code stays on host; image stays environment-only

echo "Starting MK-mini development container..."
echo "  Image:  ${IMAGE_NAME}"
echo "  Mount:  ${HOST_WS_DIR} -> /workspaces/MK-mini_ws"
echo "  Net:    host"
echo "  Mode:   privileged"
echo ""

exec docker run -it --rm \
    --name mkmini-dev \
    --network host \
    --ipc host \
    --pid host \
    --privileged \
    -v "${HOST_WS_DIR}:/workspaces/MK-mini_ws" \
    -w "/workspaces/MK-mini_ws/neupan_mkmini_ws" \
    -e "ROS_DOMAIN_ID=0" \
    -e "RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" \
    "${IMAGE_NAME}" \
    /bin/bash -c '
        echo "=== MK-mini Development Container ==="
        echo ""
        echo "ROS 2 Jazzy environment:"
        source /opt/ros/jazzy/setup.bash
        echo "  ROS_DISTRO:       ${ROS_DISTRO}"
        echo ""
        echo "Workspace contents:"
        ls -la /workspaces/MK-mini_ws/neupan_mkmini_ws/src/ 2>/dev/null || echo "  (empty — run vcs import)"
        echo ""
        echo "Quick-start:"
        echo "  1. source /opt/ros/jazzy/setup.bash"
        echo "  2. vcs import . < mkmini_neupan.repos"
        echo "  3. cp -a /workspaces/MK-mini_ws/ROS2_MK-mini/src/yhs_can_* src/"
        echo "  4. bash scripts/bootstrap_jazzy.sh"
        echo "  5. source install/setup.bash"
        echo "  6. ros2 launch mkmini_neupan_bringup full_stack.launch.py"
        echo ""
        exec /bin/bash
    '
