#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
  echo "ROS2 Jazzy is required at /opt/ros/jazzy/setup.bash" >&2
  exit 1
fi

source /opt/ros/jazzy/setup.bash

sudo apt-get update
sudo apt-get install -y \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-venv \
  python3-vcstool \
  ros-jazzy-ackermann-msgs \
  ros-jazzy-diagnostic-msgs \
  ros-jazzy-nav2-bringup \
  ros-jazzy-navigation2 \
  ros-jazzy-pointcloud-to-laserscan \
  ros-jazzy-slam-toolbox

if [[ ! -d src/neupan_ros2 || ! -d src/livox_ros_driver2 || ! -d src/FAST_LIO ]]; then
  echo "Run: vcs import . < mkmini_neupan.repos" >&2
  exit 1
fi

if [[ ! -d src/yhs_can_control || ! -d src/yhs_can_interfaces ]]; then
  echo "Copy yhs_can_control and yhs_can_interfaces into src/ before building." >&2
  exit 1
fi

sudo rosdep init 2>/dev/null || true
rosdep update
rosdep install --from-paths src --ignore-src -r -y --rosdistro jazzy

mkdir -p third_party
touch third_party/COLCON_IGNORE

python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 - <<'PY'
try:
    import torch
except ImportError as error:
    raise SystemExit(
        "Install NVIDIA's Jetson/Thor-compatible PyTorch build before NeuPAN."
    ) from error
print(f"Using PyTorch {torch.__version__}")
PY
python3 -m pip install -e third_party/NeuPAN --no-deps
python3 scripts/check_neupan_runtime.py
colcon build --symlink-install
