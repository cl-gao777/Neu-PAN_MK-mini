#!/usr/bin/env bash
# Start the real-robot MK-mini NeuPAN stack from the Thor host.
#
# Host mode:
#   bash docker/start_real_robot_neupan.sh
#
# Container mode:
#   If this script is run inside the mkmini container, it forwards directly to
#   neupan_mkmini_ws/scripts/start_real_robot_neupan.sh and does not call Docker.

set -euo pipefail

IMAGE_NAME="${MKMINI_IMAGE:-mkmini-jazzy:dev}"
CONTAINER_NAME="${MKMINI_CONTAINER_NAME:-mkmini-dev}"
HOST_WS_DIR="${MKMINI_HOST_WS:-${HOME}/workspaces/MK-mini_ws}"
CONTAINER_REPO_DIR="${MKMINI_CONTAINER_WS:-/workspaces/MK-mini_ws}"
CONTAINER_WS_DIR="${CONTAINER_REPO_DIR}/neupan_mkmini_ws"
CONTAINER_RUNNER="${CONTAINER_WS_DIR}/scripts/start_real_robot_neupan.sh"
CAN_IFACE="${CAN_IFACE:-can4}"
LIDAR_HOST_CIDR="${LIDAR_HOST_CIDR:-192.168.1.50/24}"
LIDAR_IP="${LIDAR_IP:-192.168.1.3}"

usage() {
    cat <<'EOF'
Usage:
  bash docker/start_real_robot_neupan.sh [options] [launch_arg:=value ...]

Options forwarded to the container runner:
  --neupan-config PATH
  --graph-timeout SEC
  --show-launch-output
  --dry-run

Environment overrides:
  MKMINI_HOST_WS=/path/to/MK-mini_ws
  MKMINI_IMAGE=mkmini-jazzy:dev
  MKMINI_CONTAINER_NAME=mkmini-dev
  CAN_IFACE=can4
  LIDAR_HOST_CIDR=192.168.1.50/24
  LIDAR_IP=192.168.1.3

Examples:
  bash docker/start_real_robot_neupan.sh --dry-run
  bash docker/start_real_robot_neupan.sh start_mid360:=true start_scan_pipeline:=true
  bash docker/start_real_robot_neupan.sh --neupan-config /workspaces/MK-mini_ws/neupan_mkmini_ws/config/neupan_site.yaml
EOF
}

has_arg() {
    local needle="$1"
    shift
    local arg
    for arg in "$@"; do
        if [[ "${arg}" == "${needle}" ]]; then
            return 0
        fi
    done
    return 1
}

print_command() {
    local arg
    printf '  '
    for arg in "$@"; do
        printf '%q ' "${arg}"
    done
    printf '\n'
}

inside_container() {
    [[ -f /.dockerenv || "${MKMINI_IN_CONTAINER:-}" == "1" ]]
}

forward_to_container_runner() {
    local script_dir repo_root fallback_runner
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    repo_root="$(cd "${script_dir}/.." && pwd)"
    fallback_runner="${repo_root}/neupan_mkmini_ws/scripts/start_real_robot_neupan.sh"

    if [[ -f "${CONTAINER_RUNNER}" ]]; then
        exec bash "${CONTAINER_RUNNER}" "$@"
    fi
    if [[ -f "${fallback_runner}" ]]; then
        exec bash "${fallback_runner}" "$@"
    fi

    echo "ERROR: container runner not found." >&2
    echo "Tried:" >&2
    echo "  ${CONTAINER_RUNNER}" >&2
    echo "  ${fallback_runner}" >&2
    exit 1
}

require_command() {
    local command_name="$1"
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        echo "ERROR: required command '${command_name}' not found." >&2
        exit 1
    fi
}

check_host_workspace() {
    if [[ ! -d "${HOST_WS_DIR}" ]]; then
        echo "ERROR: host workspace not found at ${HOST_WS_DIR}" >&2
        echo "Set MKMINI_HOST_WS=/path/to/MK-mini_ws if the repository lives elsewhere." >&2
        exit 1
    fi
    if [[ ! -f "${HOST_WS_DIR}/neupan_mkmini_ws/scripts/start_real_robot_neupan.sh" ]]; then
        echo "ERROR: container runner is missing from ${HOST_WS_DIR}/neupan_mkmini_ws/scripts" >&2
        exit 1
    fi
}

check_docker_image() {
    require_command docker
    if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
        echo "ERROR: Docker image '${IMAGE_NAME}' not found." >&2
        echo "Build it on Thor first:" >&2
        echo "  cd ${HOST_WS_DIR}/docker" >&2
        echo "  docker build -t ${IMAGE_NAME} ." >&2
        exit 1
    fi
}

check_can_iface() {
    local operstate_path="/sys/class/net/${CAN_IFACE}/operstate"
    if [[ ! -e "/sys/class/net/${CAN_IFACE}" ]]; then
        echo "ERROR: CAN interface '${CAN_IFACE}' does not exist on the host." >&2
        echo "Configure it on Thor before starting the container." >&2
        exit 1
    fi
    if command -v ip >/dev/null 2>&1; then
        if ! ip link show "${CAN_IFACE}" | grep -Eq '<[^>]*UP[^>]*>'; then
            echo "ERROR: CAN interface '${CAN_IFACE}' exists but is not flagged UP." >&2
            echo "Bring it up on the host before running this script." >&2
            exit 1
        fi
        return
    fi
    if [[ -r "${operstate_path}" ]]; then
        local operstate
        operstate="$(tr -d '[:space:]' < "${operstate_path}")"
        if [[ "${operstate}" != "up" && "${operstate}" != "unknown" ]]; then
            echo "ERROR: CAN interface '${CAN_IFACE}' is '${operstate}', expected 'up'." >&2
            echo "Bring it up on the host before running this script." >&2
            exit 1
        fi
    fi
}

check_lidar_host_network() {
    if ! command -v ip >/dev/null 2>&1; then
        echo "WARN: 'ip' command not found; skipping LiDAR host IP check." >&2
        return
    fi

    if ! ip -o addr show | grep -Fq "${LIDAR_HOST_CIDR}"; then
        echo "ERROR: LiDAR host CIDR '${LIDAR_HOST_CIDR}' is not configured on any host interface." >&2
        echo "Set LIDAR_HOST_CIDR to the Thor interface CIDR used by the MID-360 network." >&2
        exit 1
    fi

    if command -v ping >/dev/null 2>&1; then
        if ! ping -c 1 -W 1 "${LIDAR_IP}" >/dev/null 2>&1; then
            echo "WARN: LiDAR IP '${LIDAR_IP}' did not answer one ping; continuing because ICMP may be blocked." >&2
        fi
    fi
}

container_running_id() {
    docker ps \
        --filter "name=^/${CONTAINER_NAME}$" \
        --filter "status=running" \
        --quiet
}

container_exists_id() {
    docker ps --all \
        --filter "name=^/${CONTAINER_NAME}$" \
        --quiet
}

run_in_existing_container() {
    echo "Reusing running container '${CONTAINER_NAME}'."
    exec docker exec -it \
        -e MKMINI_IN_CONTAINER=1 \
        -w "${CONTAINER_WS_DIR}" \
        "${CONTAINER_NAME}" \
        /bin/bash -lc 'exec bash "$1" "${@:2}"' \
        mkmini-real-robot-runner "${CONTAINER_RUNNER}" "$@"
}

start_temporary_container() {
    echo "Starting '${CONTAINER_NAME}' from image '${IMAGE_NAME}'."
    exec docker run -it --rm \
        --name "${CONTAINER_NAME}" \
        --network host \
        --ipc host \
        --pid host \
        --privileged \
        -v "${HOST_WS_DIR}:${CONTAINER_REPO_DIR}" \
        -w "${CONTAINER_WS_DIR}" \
        -e "MKMINI_IN_CONTAINER=1" \
        -e "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}" \
        -e "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}" \
        "${IMAGE_NAME}" \
        /bin/bash -lc 'exec bash "$1" "${@:2}"' \
        mkmini-real-robot-runner "${CONTAINER_RUNNER}" "$@"
}

dry_run() {
    echo "DRY RUN: host-side checks and container action only."
    echo ""
    echo "Host checks that would run:"
    echo "  workspace: ${HOST_WS_DIR}"
    echo "  docker image: ${IMAGE_NAME}"
    echo "  CAN interface: ${CAN_IFACE} exists and is up"
    echo "  LiDAR host CIDR: ${LIDAR_HOST_CIDR}"
    echo "  LiDAR ping target: ${LIDAR_IP} (warning only)"
    echo ""
    echo "If already inside a container, this script would run:"
    print_command bash "${CONTAINER_RUNNER}" "$@"
    echo ""
    echo "If '${CONTAINER_NAME}' is already running, this script would run:"
    print_command docker exec -it -e MKMINI_IN_CONTAINER=1 -w "${CONTAINER_WS_DIR}" \
        "${CONTAINER_NAME}" /bin/bash -lc \
        'exec bash "$1" "${@:2}"' \
        mkmini-real-robot-runner "${CONTAINER_RUNNER}" "$@"
    echo ""
    echo "Otherwise it would start:"
    print_command docker run -it --rm --name "${CONTAINER_NAME}" --network host --ipc host --pid host \
        --privileged -v "${HOST_WS_DIR}:${CONTAINER_REPO_DIR}" -w "${CONTAINER_WS_DIR}" \
        -e "MKMINI_IN_CONTAINER=1" -e "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}" \
        -e "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}" "${IMAGE_NAME}" \
        /bin/bash -lc 'exec bash "$1" "${@:2}"' \
        mkmini-real-robot-runner "${CONTAINER_RUNNER}" "$@"
}

if has_arg "--help" "$@" || has_arg "-h" "$@"; then
    usage
    exit 0
fi

if inside_container; then
    forward_to_container_runner "$@"
fi

if has_arg "--dry-run" "$@"; then
    dry_run "$@"
    exit 0
fi

check_host_workspace
check_docker_image
check_can_iface
check_lidar_host_network

if [[ -n "$(container_running_id)" ]]; then
    run_in_existing_container "$@"
fi

if [[ -n "$(container_exists_id)" ]]; then
    echo "ERROR: container '${CONTAINER_NAME}' exists but is not running." >&2
    echo "Start it, rename it, or remove it manually before using this one-click launcher." >&2
    exit 1
fi

start_temporary_container "$@"
