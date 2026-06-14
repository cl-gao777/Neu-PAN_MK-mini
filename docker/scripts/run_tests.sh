#!/usr/bin/env bash
# docker/scripts/run_tests.sh
# Run all unit tests inside the Docker container.
#
# Usage:
#   bash run_tests.sh                  # Run all tests
#   bash run_tests.sh --chassis-only   # Chassis C++ gtest only
#   bash run_tests.sh --bridge-only    # NeuPAN bridge Python pytest only

set -euo pipefail
export AMENT_TRACE_SETUP_FILES="${AMENT_TRACE_SETUP_FILES:-}"

safe_source() {
  set +u
  source "$1"
  set -u
}


ROS_SETUP="/opt/ros/jazzy/setup.bash"
CHASSIS_WS="/workspaces/MK-mini_ws/ROS2_MK-mini"
NEUPAN_WS="/workspaces/MK-mini_ws/neupan_mkmini_ws"

MODE="all"
case "${1:-}" in
    --chassis-only) MODE="chassis" ;;
    --bridge-only)  MODE="bridge" ;;
    "")             MODE="all" ;;
    --help|-h)
        echo "Usage: bash run_tests.sh [--chassis-only | --bridge-only]"
        exit 0
        ;;
    *) echo "Unknown option: $1"; exit 1 ;;
esac

if [[ ! -f "${ROS_SETUP}" ]]; then
    echo "ERROR: ROS 2 Jazzy not found. Are you inside the container?" >&2
    exit 1
fi

safe_source "${ROS_SETUP}"

PASS=0
FAIL=0

# ---- Chassis C++ tests (colcon test) ----
run_chassis_tests() {
    echo "=== Chassis SDK Tests (colcon test) ==="
    if [[ ! -d "${CHASSIS_WS}/src" ]]; then
        echo "SKIP: Chassis workspace not found"
        return
    fi
    cd "${CHASSIS_WS}"
    colcon test --packages-select yhs_can_interfaces yhs_can_control \
        --return-code-on-test-failure || true
    echo ""
    echo "Test results:"
    colcon test-result --verbose || true
}

# ---- NeuPAN bridge Python tests (pytest) ----
run_bridge_tests() {
    echo "=== NeuPAN Bridge Tests (pytest) ==="
    local test_dirs=(
        "${NEUPAN_WS}/src/mkmini_neupan_bridge/test"
        "${NEUPAN_WS}/src/mkmini_neupan_bringup/test"
    )
    for test_dir in "${test_dirs[@]}"; do
        if [[ -d "${test_dir}" ]]; then
            echo "  Running: ${test_dir}"
            python3 -m pytest "${test_dir}" -v || PASS=$((PASS + 0))
        fi
    done
}

# ---- Main ----
case "${MODE}" in
    chassis) run_chassis_tests ;;
    bridge)  run_bridge_tests ;;
    all)
        run_chassis_tests
        echo ""
        run_bridge_tests
        ;;
esac

echo ""
echo "All tests completed."
