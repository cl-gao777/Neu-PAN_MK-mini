#!/usr/bin/env bash
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${workspace_root}"

vendor_src="${1:-${MKMINI_VENDOR_SRC:-}}"

required_repos=(
  "src/neupan_ros2"
  "src/livox_ros_driver2"
  "src/FAST_LIO"
  "third_party/yhs_robot_description"
  "third_party/NeuPAN"
  "third_party/ir-sim"
)

required_vendor_packages=(
  "yhs_can_control"
  "yhs_can_interfaces"
)

required_vendor_dirs=(
  "src/yhs_can_control"
  "src/yhs_can_interfaces"
)

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  local command_name="$1"
  local install_hint="$2"

  if ! command -v "${command_name}" >/dev/null 2>&1; then
    fail "${command_name} is required. ${install_hint}"
  fi
}

copy_vendor_package() {
  local package_name="$1"

  if [[ -d "src/${package_name}" ]]; then
    echo "OK src/${package_name}"
    return
  fi

  if [[ -z "${vendor_src}" ]]; then
    fail "src/${package_name} is missing. Pass /path/to/ROS2_MK-mini/src as the first argument or set MKMINI_VENDOR_SRC."
  fi

  if [[ -d "${vendor_src}/${package_name}" ]]; then
    mkdir -p src
    cp -a "${vendor_src}/${package_name}" src/
  elif [[ -d "${vendor_src}/src/${package_name}" ]]; then
    mkdir -p src
    cp -a "${vendor_src}/src/${package_name}" src/
  else
    fail "Could not find ${package_name} under ${vendor_src} or ${vendor_src}/src."
  fi

  echo "Copied src/${package_name}"
}

check_directory() {
  local path="$1"

  if [[ ! -d "${path}" ]]; then
    echo "MISSING ${path}" >&2
    return 1
  fi

  echo "OK ${path}"
}

repos_file="mkmini_neupan.lock.repos"
if [[ ! -f "${repos_file}" ]]; then
  repos_file="mkmini_neupan.repos"
fi

if [[ ! -f "${repos_file}" ]]; then
  fail "Run this script from the neupan_mkmini_ws workspace or keep mkmini_neupan.repos at the workspace root."
fi

require_command "vcs" "Install it with: sudo apt-get install -y python3-vcstool"

# Older workspace revisions imported the reference-only YHS description
# collection under src/. It contains many ROS1/ROS2 packages with duplicate
# names, so rosdep and colcon must not recursively scan it. Migrate it before
# vcs import; third_party/ is excluded from colcon by bootstrap_jazzy.sh.
if [[ -d src/yhs_robot_description && ! -e third_party/yhs_robot_description ]]; then
  mkdir -p third_party
  mv src/yhs_robot_description third_party/yhs_robot_description
  echo "Moved reference descriptions to third_party/yhs_robot_description"
fi

echo "Importing upstream repositories from ${repos_file}..."
vcs import . < "${repos_file}"

echo "Freezing exact imported revisions..."
bash scripts/freeze_revisions.sh

for package_name in "${required_vendor_packages[@]}"; do
  copy_vendor_package "${package_name}"
done

missing=0
for path in "${required_repos[@]}"; do
  check_directory "${path}" || missing=1
done

for path in "${required_vendor_dirs[@]}"; do
  check_directory "${path}" || missing=1
done

if [[ "${missing}" -ne 0 ]]; then
  fail "Source import is incomplete. Fix the missing directories above, then rerun this script."
fi

echo "Source import complete. Next: bash scripts/bootstrap_jazzy.sh"
