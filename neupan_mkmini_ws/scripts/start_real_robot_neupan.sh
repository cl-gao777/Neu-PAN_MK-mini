#!/usr/bin/env bash
# Container-side real-robot runner for MK-mini NeuPAN.
#
# This script runs the Thor NeuPAN preflight first. NeuPAN is launched only
# after preflight returns PASS.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DEFAULT_LAUNCH_ARGS=(
    "start_mid360:=true"
    "start_fast_lio:=true"
    "start_visualization_cloud:=false"
    "start_scan_pipeline:=true"
    "start_slam:=false"
    "start_navigation:=false"
    "start_fast_lio_tf:=true"
)

DRY_RUN=0
SHOW_LAUNCH_OUTPUT=0
GRAPH_TIMEOUT=""
NEUPAN_CONFIG=""
LAUNCH_ARGS=("${DEFAULT_LAUNCH_ARGS[@]}")
IGNORED_START_NEUPAN=0
LAUNCH_PID=""
SHOULD_DISARM=0
DISARMED=0

usage() {
    cat <<'EOF'
Usage:
  bash scripts/start_real_robot_neupan.sh [options] [launch_arg:=value ...]

Options:
  --neupan-config PATH      Validate and launch with this NeuPAN config.
  --graph-timeout SEC       Time allowed for preflight ROS graph checks.
  --show-launch-output      Show pre-NeuPAN launch output during preflight.
  --dry-run                 Print commands without sourcing ROS or launching.

Default launch arguments:
  start_mid360:=true
  start_fast_lio:=true
  start_visualization_cloud:=false
  start_scan_pipeline:=true
  start_slam:=false
  start_navigation:=false
  start_fast_lio_tf:=true

Notes:
  start_neupan:=... is ignored here. Preflight forces false; final launch
  forces true after preflight passes.
EOF
}

print_command() {
    local arg
    printf '  '
    for arg in "$@"; do
        printf '%q ' "${arg}"
    done
    printf '\n'
}

set_launch_arg() {
    local new_arg="$1"
    local key="${new_arg%%:=*}"
    local kept=()
    local existing
    for existing in "${LAUNCH_ARGS[@]}"; do
        if [[ "${existing}" != "${key}:="* ]]; then
            kept+=("${existing}")
        fi
    done
    kept+=("${new_arg}")
    LAUNCH_ARGS=("${kept[@]}")
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                usage
                exit 0
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --show-launch-output)
                SHOW_LAUNCH_OUTPUT=1
                shift
                ;;
            --graph-timeout)
                if [[ $# -lt 2 ]]; then
                    echo "ERROR: --graph-timeout requires a value." >&2
                    exit 2
                fi
                GRAPH_TIMEOUT="$2"
                shift 2
                ;;
            --neupan-config)
                if [[ $# -lt 2 ]]; then
                    echo "ERROR: --neupan-config requires a path." >&2
                    exit 2
                fi
                if [[ -n "${NEUPAN_CONFIG}" && "${NEUPAN_CONFIG}" != "$2" ]]; then
                    echo "ERROR: conflicting NeuPAN config values." >&2
                    exit 2
                fi
                NEUPAN_CONFIG="$2"
                shift 2
                ;;
            start_neupan:=*)
                IGNORED_START_NEUPAN=1
                shift
                ;;
            neupan_config:=*)
                local value="${1#neupan_config:=}"
                if [[ -n "${NEUPAN_CONFIG}" && "${NEUPAN_CONFIG}" != "${value}" ]]; then
                    echo "ERROR: conflicting NeuPAN config values." >&2
                    exit 2
                fi
                NEUPAN_CONFIG="${value}"
                shift
                ;;
            *:=*)
                set_launch_arg "$1"
                shift
                ;;
            *)
                echo "ERROR: unknown argument '$1'." >&2
                usage >&2
                exit 2
                ;;
        esac
    done

    if [[ -n "${NEUPAN_CONFIG}" ]]; then
        set_launch_arg "neupan_config:=${NEUPAN_CONFIG}"
    fi
}

build_preflight_command() {
    PREFLIGHT_CMD=(ros2 run mkmini_neupan_bringup thor_neupan_preflight)
    if [[ -n "${NEUPAN_CONFIG}" ]]; then
        PREFLIGHT_CMD+=(--neupan-config "${NEUPAN_CONFIG}")
    fi
    if [[ -n "${GRAPH_TIMEOUT}" ]]; then
        PREFLIGHT_CMD+=(--graph-timeout "${GRAPH_TIMEOUT}")
    fi
    if [[ "${SHOW_LAUNCH_OUTPUT}" == "1" ]]; then
        PREFLIGHT_CMD+=(--show-launch-output)
    fi
    PREFLIGHT_CMD+=("${LAUNCH_ARGS[@]}")
}

build_launch_command() {
    LAUNCH_CMD=(ros2 launch mkmini_neupan_bringup full_stack.launch.py)
    LAUNCH_CMD+=("${LAUNCH_ARGS[@]}")
    LAUNCH_CMD+=("start_neupan:=true")
}

source_environment() {
    if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
        echo "ERROR: /opt/ros/jazzy/setup.bash not found. This runner expects ROS 2 Jazzy." >&2
        exit 1
    fi
    # shellcheck source=/dev/null
    source /opt/ros/jazzy/setup.bash

    if [[ -f "${WS_DIR}/.venv/bin/activate" ]]; then
        # shellcheck source=/dev/null
        source "${WS_DIR}/.venv/bin/activate"
    fi

    if [[ ! -f "${WS_DIR}/install/setup.bash" ]]; then
        echo "ERROR: ${WS_DIR}/install/setup.bash not found." >&2
        echo "Build the workspace first with scripts/bootstrap_jazzy.sh or colcon build." >&2
        exit 1
    fi
    # shellcheck source=/dev/null
    source "${WS_DIR}/install/setup.bash"
}

disarm_bridge_once() {
    if [[ "${SHOULD_DISARM}" != "1" || "${DISARMED}" == "1" ]]; then
        return
    fi
    DISARMED=1
    echo ""
    echo "Best-effort disarm: disabling NeuPAN bridge and asserting software emergency stop."
    bash "${SCRIPT_DIR}/disarm_bridge.sh" || true
}

cleanup() {
    local status=$?
    if [[ -n "${LAUNCH_PID}" ]]; then
        disarm_bridge_once
        sleep 0.5
        kill -INT "${LAUNCH_PID}" >/dev/null 2>&1 || true
        wait "${LAUNCH_PID}" >/dev/null 2>&1 || true
        LAUNCH_PID=""
    else
        disarm_bridge_once
    fi
    exit "${status}"
}

parse_args "$@"
build_preflight_command
build_launch_command

if [[ "${DRY_RUN}" == "1" ]]; then
    echo "DRY RUN: container-side NeuPAN launch sequence."
    if [[ "${IGNORED_START_NEUPAN}" == "1" ]]; then
        echo "WARN: start_neupan:=... would be ignored; preflight and final launch set it explicitly."
    fi
    echo ""
    echo "Would source:"
    echo "  /opt/ros/jazzy/setup.bash"
    echo "  ${WS_DIR}/.venv/bin/activate (if present)"
    echo "  ${WS_DIR}/install/setup.bash"
    echo ""
    echo "Would run preflight:"
    print_command "${PREFLIGHT_CMD[@]}"
    echo ""
    echo "If preflight passes, would run:"
    print_command "${LAUNCH_CMD[@]}"
    echo ""
    echo "On shutdown, would run:"
    print_command bash "${SCRIPT_DIR}/disarm_bridge.sh"
    exit 0
fi

cd "${WS_DIR}"
source_environment

if [[ "${IGNORED_START_NEUPAN}" == "1" ]]; then
    echo "WARN: ignoring user-provided start_neupan argument; this runner controls it."
fi

echo "Running Thor NeuPAN preflight..."
print_command "${PREFLIGHT_CMD[@]}"
"${PREFLIGHT_CMD[@]}"

echo ""
echo "Preflight passed. Starting NeuPAN full stack."
echo "This script does not arm or unlock the safety bridge."
print_command "${LAUNCH_CMD[@]}"

SHOULD_DISARM=1
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

"${LAUNCH_CMD[@]}" &
LAUNCH_PID=$!
if wait "${LAUNCH_PID}"; then
    LAUNCH_STATUS=0
else
    LAUNCH_STATUS=$?
fi
LAUNCH_PID=""
exit "${LAUNCH_STATUS}"
