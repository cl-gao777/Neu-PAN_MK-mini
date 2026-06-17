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

required_sources=(
  "src/neupan_ros2"
  "src/livox_ros_driver2"
  "src/FAST_LIO"
  "third_party/NeuPAN"
)

for source_dir in "${required_sources[@]}"; do
  if [[ ! -d "${source_dir}" ]]; then
    echo "Missing ${source_dir}" >&2
    echo "Run: bash scripts/import_upstreams.sh /path/to/ROS2_MK-mini/src" >&2
    exit 1
  fi
done

if [[ ! -d src/yhs_can_control || ! -d src/yhs_can_interfaces ]]; then
  echo "Copy yhs_can_control and yhs_can_interfaces into src/ before building." >&2
  echo "Run: bash scripts/import_upstreams.sh /path/to/ROS2_MK-mini/src" >&2
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
