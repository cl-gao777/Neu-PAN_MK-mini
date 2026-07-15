#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
  echo "ROS2 Jazzy is required at /opt/ros/jazzy/setup.bash" >&2
  exit 1
fi

# ROS-generated setup files read optional variables before assigning defaults;
# temporarily disable nounset while sourcing the underlay, then restore it for
# the remainder of this bootstrap script.
set +u
source /opt/ros/jazzy/setup.bash
set -u

profile="core"
if [[ "${1:-}" == "--profile" ]]; then
  profile="${2:-}"
  shift 2
fi
if [[ "$#" -ne 0 || ! "${profile}" =~ ^(core|nav2-planner|full-debug)$ ]]; then
  echo "Usage: bash scripts/bootstrap_jazzy.sh [--profile core|nav2-planner|full-debug]" >&2
  exit 2
fi

apt_packages=(
  python3-colcon-common-extensions
  python3-rosdep
  python3-tk
  python3-venv
  python3-vcstool
  ros-jazzy-ackermann-msgs
  ros-jazzy-diagnostic-msgs
  ros-jazzy-pointcloud-to-laserscan
)

if [[ "${profile}" == "nav2-planner" || "${profile}" == "full-debug" ]]; then
  apt_packages+=(
    ros-jazzy-nav2-costmap-2d
    ros-jazzy-nav2-lifecycle-manager
    ros-jazzy-nav2-map-server
    ros-jazzy-nav2-msgs
    ros-jazzy-nav2-navfn-planner
    ros-jazzy-nav2-planner
    ros-jazzy-nav2-smac-planner
    ros-jazzy-nav2-theta-star-planner
  )
fi

if [[ "${profile}" == "full-debug" ]]; then
  apt_packages+=(
    ros-jazzy-nav2-bringup
    ros-jazzy-navigation2
    ros-jazzy-rviz2
    ros-jazzy-slam-toolbox
  )
fi

sudo apt-get -o Acquire::Retries=10 update
sudo apt-get -o Acquire::Retries=10 install -y "${apt_packages[@]}"

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

if [[ ! -f /usr/local/lib/liblivox_lidar_sdk_shared.so ]] \
  || [[ ! -f /usr/local/include/livox_lidar_api.h ]] \
  || ! grep -Fq "liblivox_lidar_sdk_shared.so" < <(ldconfig -p 2>/dev/null); then
  echo "Livox-SDK2 is missing from the container image." >&2
  echo "Rebuild docker/Dockerfile with the pinned Livox-SDK2 release." >&2
  exit 1
fi

# Livox ships ROS-specific manifests and launch trees instead of a ready-to-scan
# ROS package. Reproduce the non-building preparation performed by the official
# `build.sh jazzy` without letting that script delete the shared workspace's
# build/install directories or start a nested colcon build.
livox_source="src/livox_ros_driver2"
if [[ ! -f "${livox_source}/package_ROS2.xml" ]]; then
  echo "Missing ${livox_source}/package_ROS2.xml" >&2
  exit 1
fi
if [[ ! -d "${livox_source}/launch_ROS2" ]]; then
  echo "Missing ${livox_source}/launch_ROS2" >&2
  exit 1
fi
cp -f "${livox_source}/package_ROS2.xml" "${livox_source}/package.xml"
mkdir -p "${livox_source}/launch"
cp -a "${livox_source}/launch_ROS2/." "${livox_source}/launch/"

# Prepare FAST-LIO's pinned ikd-Tree submodule and use the C++17
# language level required by ROS 2 Jazzy. This changes build configuration
# only; FAST-LIO algorithm sources remain untouched.
fast_lio_source="src/FAST_LIO"
if [[ ! -f "${fast_lio_source}/.gitmodules" ]]; then
  echo "Missing ${fast_lio_source}/.gitmodules" >&2
  exit 1
fi

git -C "${fast_lio_source}" submodule update --init --recursive

expected_ikd_tree_commit="$(
  git -C "${fast_lio_source}" ls-tree HEAD include/ikd-Tree | awk '{print $3}'
)"
actual_ikd_tree_commit="$(
  git -C "${fast_lio_source}/include/ikd-Tree" rev-parse HEAD
)"

if [[ -z "${expected_ikd_tree_commit}" ]] \
  || [[ "${actual_ikd_tree_commit}" != "${expected_ikd_tree_commit}" ]]; then
  echo "FAST-LIO ikd-Tree revision mismatch." >&2
  exit 1
fi

test -f "${fast_lio_source}/include/ikd-Tree/ikd_Tree.cpp"

sed -i \
  -e "s/-std=c++14/-std=c++17/g" \
  -e "s/-std=c++0x/-std=c++17/g" \
  -e "s/set(CMAKE_CXX_STANDARD 14)/set(CMAKE_CXX_STANDARD 17)/" \
  "${fast_lio_source}/CMakeLists.txt"

if grep -Eq "c\+\+14|c\+\+0x|CXX_STANDARD 14" \
  "${fast_lio_source}/CMakeLists.txt"; then
  echo "FAST-LIO still contains a pre-C++17 build flag." >&2
  exit 1
fi

sudo rosdep init 2>/dev/null || true
rosdep update
rosdep_paths=(
  src/neupan_ros2/src/neupan_ros2
  src/livox_ros_driver2
  src/FAST_LIO
  src/yhs_can_control
  src/yhs_can_interfaces
  src/mkmini_neupan_bridge
  src/mkmini_neupan_bringup
)
rosdep install \
  --from-paths "${rosdep_paths[@]}" \
  --ignore-src -r -y --rosdistro jazzy

mkdir -p third_party
touch third_party/COLCON_IGNORE

python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 scripts/check_neupan_runtime.py --torch-lock-only
python3 -m pip install -r requirements-thor.txt
python3 -m pip install -e third_party/NeuPAN --no-deps
python3 scripts/check_neupan_runtime.py

# NVIDIA's container sets OPAL_PREFIX=/usr/local/mpi for HPC-X. That variable
# also relocates Ubuntu's /usr/bin/mpicc wrapper and produces non-existent
# /usr/local/mpi/lib/aarch64-linux-gnu paths. Build ROS/PCL/VTK packages with
# the matching Ubuntu OpenMPI toolchain; the image-level LD_LIBRARY_PATH still
# retains HPC-X for NVIDIA Torch in separate Python processes.
unset OPAL_PREFIX OPAL_DESTDIR

# NGC setuptools 81 removed options still used by ROS Jazzy colcon.
# Scope Ubuntu setuptools 68 to colcon only; NeuPAN keeps its normal venv.
colcon_pythonpath="/usr/lib/python3/dist-packages${PYTHONPATH:+:${PYTHONPATH}}"
PYTHONPATH="${colcon_pythonpath}" colcon build \
  --symlink-install \
  --packages-skip ddr_minimal_sim \
  --cmake-args \
    -DROS_EDITION=ROS2 \
    -DDISTRO_ROS=jazzy \
    -DMPI_C_COMPILER=/usr/bin/mpicc \
    -DMPI_CXX_COMPILER=/usr/bin/mpicxx
