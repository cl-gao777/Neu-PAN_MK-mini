#!/usr/bin/env bash
# Safe interactive Docker entrypoint for MK-mini NeuPAN on NVIDIA Thor.
#
# Default:
#   Offline development mode. GPU enabled, network isolated, no hardware access.
#
# Hardware mode:
#   Explicitly enables host networking, host IPC/PID and privileged device access.
#   This mode still starts only a shell; it does not launch ROS nodes.
#
# Usage:
#   bash run_mkmini_dev.sh
#   bash run_mkmini_dev.sh --offline
#   bash run_mkmini_dev.sh --hardware
#   bash run_mkmini_dev.sh --dry-run
#   bash run_mkmini_dev.sh --image IMAGE --name CONTAINER

set -euo pipefail

DEFAULT_IMAGE="mkmini-jazzy:thor-ngc26.06-core-sdk2-20260714"
IMAGE_NAME="${MKMINI_IMAGE:-${DEFAULT_IMAGE}}"
CONTAINER_NAME="${MKMINI_CONTAINER_NAME:-mkmini-dev}"
HOST_WS_DIR="${MKMINI_HOST_WS:-${HOME}/workspaces/MK-mini_ws}"
RUNTIME_MANIFEST="/etc/mkmini/thor-runtime.lock.json"

MODE="offline"
DRY_RUN="false"

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

usage() {
  printf '%s\n' \
    "Usage: bash run_mkmini_dev.sh [OPTIONS]" \
    "" \
    "Options:" \
    "  --offline       Safe offline mode (default)" \
    "  --hardware      Enable host network and hardware access" \
    "  --image IMAGE   Override Docker image" \
    "  --name NAME     Override container name" \
    "  --dry-run       Print docker command without starting it" \
    "  -h, --help      Show this help" \
    "" \
    "Environment overrides:" \
    "  MKMINI_IMAGE" \
    "  MKMINI_CONTAINER_NAME" \
    "  MKMINI_HOST_WS" \
    "  MKMINI_ROS_DOMAIN_ID"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --offline)
      MODE="offline"
      ;;
    --hardware)
      MODE="hardware"
      ;;
    --image)
      shift
      [[ "$#" -gt 0 ]] || {
        echo "ERROR: --image requires a value" >&2
        exit 2
      }
      IMAGE_NAME="$1"
      ;;
    --name)
      shift
      [[ "$#" -gt 0 ]] || {
        echo "ERROR: --name requires a value" >&2
        exit 2
      }
      CONTAINER_NAME="$1"
      ;;
    --dry-run)
      DRY_RUN="true"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ ! -d "${HOST_WS_DIR}/neupan_mkmini_ws" ]]; then
  echo "ERROR: workspace not found: ${HOST_WS_DIR}/neupan_mkmini_ws" >&2
  exit 1
fi

if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo "ERROR: Docker image not found: ${IMAGE_NAME}" >&2
  echo "Override it with: --image mkmini-jazzy:dev" >&2
  exit 1
fi

if docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
  echo "ERROR: container name already exists: ${CONTAINER_NAME}" >&2
  echo "Inspect it with: docker ps -a --filter name=${CONTAINER_NAME}" >&2
  exit 1
fi

common_args=(
  run
  -it
  --rm
  --platform linux/arm64
  --runtime nvidia
  --name "${CONTAINER_NAME}"
  -v "${HOST_WS_DIR}:/workspaces/MK-mini_ws"
  -w /workspaces/MK-mini_ws/neupan_mkmini_ws
  -e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  -e NVIDIA_VISIBLE_DEVICES=all
  -e MKMINI_THOR_RUNTIME_MANIFEST=${RUNTIME_MANIFEST}
  -e MKMINI_MODE="${MODE}"
  -e MKMINI_HOST_UID="${HOST_UID}"
  -e MKMINI_HOST_GID="${HOST_GID}"
)

if [[ "${MODE}" == "offline" ]]; then
  ROS_DOMAIN="${MKMINI_ROS_DOMAIN_ID:-218}"
  mode_args=(
    --network none
    --shm-size 1g
    -e ROS_DOMAIN_ID="${ROS_DOMAIN}"
    -e ROS_LOCALHOST_ONLY=1
    -e NVIDIA_DRIVER_CAPABILITIES=compute,utility
  )
else
  ROS_DOMAIN="${MKMINI_ROS_DOMAIN_ID:-0}"
  mode_args=(
    --network host
    --ipc host
    --pid host
    --privileged
    -e ROS_DOMAIN_ID="${ROS_DOMAIN}"
    -e ROS_LOCALHOST_ONLY=0
    -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,video
  )
fi

shell_command='
set -e
cd /workspaces/MK-mini_ws/neupan_mkmini_ws

source /opt/ros/jazzy/setup.bash

if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
else
  echo "WARNING: .venv/bin/activate not found"
fi

if [[ -f install/setup.bash ]]; then
  source install/setup.bash
else
  echo "WARNING: install/setup.bash not found"
fi

echo
echo "=== MK-mini NeuPAN Development Shell ==="
echo "Mode:              ${MKMINI_MODE}"
echo "Image environment: NVIDIA Thor / ROS 2 Jazzy"
echo "ROS_DOMAIN_ID:     ${ROS_DOMAIN_ID}"
echo "ROS_LOCALHOST_ONLY:${ROS_LOCALHOST_ONLY}"
echo "Workspace:         /workspaces/MK-mini_ws/neupan_mkmini_ws"
echo
echo "No ROS, CAN, LiDAR, FAST-LIO or control nodes were started."
echo

python3 -c "import torch; print(\"Torch:\", torch.__version__); print(\"CUDA available:\", torch.cuda.is_available())"

export PS1="(mkmini-${MKMINI_MODE}) \u@\h:\w\\$ "

set +e
/bin/bash --noprofile --norc -i
shell_status=$?
set -e

if [[ "$(id -u)" -eq 0 ]]; then
  echo
  echo "Restoring workspace ownership to ${MKMINI_HOST_UID}:${MKMINI_HOST_GID}..."
  chown -R     "${MKMINI_HOST_UID}:${MKMINI_HOST_GID}"     /workspaces/MK-mini_ws/neupan_mkmini_ws
  echo "Workspace ownership restored."
fi

exit "${shell_status}"
'

docker_args=(
  "${common_args[@]}"
  "${mode_args[@]}"
  "${IMAGE_NAME}"
  /bin/bash
  -lc
  "${shell_command}"
)

echo "=== MK-mini container configuration ==="
echo "Mode:       ${MODE}"
echo "Image:      ${IMAGE_NAME}"
echo "Container:  ${CONTAINER_NAME}"
echo "Workspace:  ${HOST_WS_DIR}"
echo "ROS domain: ${ROS_DOMAIN}"
echo "Host owner: ${HOST_UID}:${HOST_GID}"

if [[ "${MODE}" == "offline" ]]; then
  echo "Network:    isolated"
  echo "Hardware:   disabled"
else
  echo "Network:    host"
  echo "Hardware:   privileged"
  echo "WARNING: hardware mode exposes Livox UDP, SocketCAN and host devices."
fi

echo

if [[ "${DRY_RUN}" == "true" ]]; then
  printf 'DRY RUN:'
  printf ' %q' docker "${docker_args[@]}"
  printf '\n'
  exit 0
fi

exec docker "${docker_args[@]}"
