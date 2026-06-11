#!/usr/bin/env bash
# docker/scripts/check_can.sh
# Check CAN interface status and optionally dump frames.
# Run inside the Docker container.
#
# Usage:
#   bash check_can.sh              # Quick status check
#   bash check_can.sh 5            # Status + candump for 5 seconds
#   bash check_can.sh 0            # Status + continuous candump

set -euo pipefail

CAN_IFACE="can0"
DURATION="${1:--1}"   # -1 = status only, 0 = continuous, N = seconds

echo "=== CAN Interface Status ==="

if [[ ! -e "/sys/class/net/${CAN_IFACE}" ]]; then
    echo "ERROR: ${CAN_IFACE} interface not found." >&2
    echo "" >&2
    echo "The CAN interface must be configured on the Thor HOST before starting" >&2
    echo "the container. On the Thor host, run:" >&2
    echo "  sudo ip link set ${CAN_IFACE} type can bitrate 500000" >&2
    echo "  sudo ip link set ${CAN_IFACE} up" >&2
    exit 1
fi

CAN_STATE=$(cat "/sys/class/net/${CAN_IFACE}/operstate" 2>/dev/null || echo "unknown")
echo "  Interface: ${CAN_IFACE}"
echo "  State:     ${CAN_STATE}"

ip -details link show "${CAN_IFACE}" 2>/dev/null | grep -E 'can[0-9]*:|bitrate|state' || true

if [[ "${CAN_STATE}" != "UP" ]]; then
    echo ""
    echo "WARNING: ${CAN_IFACE} is not UP. Bring it up on the Thor host:" >&2
    echo "  sudo ip link set ${CAN_IFACE} up" >&2
    exit 1
fi

if [[ "${DURATION}" == "-1" ]]; then
    echo ""
    echo "Run with a duration to capture frames:"
    echo "  bash check_can.sh 5"
    exit 0
fi

echo ""
echo "Listening on ${CAN_IFACE}..."

if [[ "${DURATION}" == "0" ]]; then
    echo "(Press Ctrl+C to stop)"
    candump "${CAN_IFACE}"
else
    timeout "${DURATION}" candump "${CAN_IFACE}" || true
    echo ""
    echo "Capture complete (${DURATION}s)."
fi
