# NVIDIA Thor development image for MK-mini NeuPAN.
#
# Target host validated by the operator:
#   JetPack 7.2 / L4T R39.2 / driver 595.78 / CUDA 13.2 / aarch64.
#
# The NVIDIA PyTorch multi-architecture image owns CUDA, cuDNN and GPU Torch;
# its confirmed linux/arm64 manifest is selected on Thor.
# ROS 2 Jazzy is installed on top. Source code remains bind-mounted.

ARG PYTORCH_BASE_IMAGE=nvcr.io/nvidia/pytorch:26.06-py3
FROM ${PYTORCH_BASE_IMAGE} AS neupan-core

ARG PYTORCH_BASE_IMAGE
ARG ROS_DISTRO=jazzy
ARG UBUNTU_PORTS_MIRROR=https://mirrors.ustc.edu.cn/ubuntu-ports
ARG ROS2_APT_MIRROR=https://mirrors.ustc.edu.cn/ros2/ubuntu
ARG APT_MIRROR_HOST=mirrors.ustc.edu.cn
ARG APT_RETRIES=10
ARG LIVOX_SDK2_REPOSITORY=https://github.com/Livox-SDK/Livox-SDK2.git
ARG LIVOX_SDK2_TAG=v1.3.1
ARG LIVOX_SDK2_COMMIT=f5d9375f84efe2b15bc0a052d3e18482ed13adf4
ARG LIVOX_SDK2_ARCHIVE_SHA256=f469dc57b38cd64c71381eb54d9525bfc3574feb0152c2b65239283107c4fa29

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=${ROS_DISTRO}
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV MKMINI_PYTORCH_BASE_IMAGE=${PYTORCH_BASE_IMAGE}
ENV MKMINI_THOR_RUNTIME_MANIFEST=/etc/mkmini/thor-runtime.lock.json
ENV MKMINI_LIVOX_SDK2_REPOSITORY=${LIVOX_SDK2_REPOSITORY}
ENV MKMINI_LIVOX_SDK2_COMMIT=${LIVOX_SDK2_COMMIT}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Use the measured-fast ARM64 mirror by default. All mirror arguments remain
# overridable so an operator can fall back to the official repositories.
# Per-host DIRECT rules keep a local HTTP(S) proxy from returning a late 502
# after hundreds of packages have already downloaded. Retries and timeouts are
# retained in the image because bootstrap_jazzy.sh also uses apt.
RUN find /etc/apt -type f \( -name '*.list' -o -name '*.sources' \) -print0 \
      | xargs -0 -r sed -i \
        -e "s|http://ports.ubuntu.com/ubuntu-ports|${UBUNTU_PORTS_MIRROR}|g" \
        -e "s|https://ports.ubuntu.com/ubuntu-ports|${UBUNTU_PORTS_MIRROR}|g" \
    && printf '%s\n' \
      "Acquire::Retries \"${APT_RETRIES}\";" \
      'Acquire::http::Timeout "30";' \
      'Acquire::https::Timeout "30";' \
      "Acquire::http::Proxy::${APT_MIRROR_HOST} \"DIRECT\";" \
      "Acquire::https::Proxy::${APT_MIRROR_HOST} \"DIRECT\";" \
      > /etc/apt/apt.conf.d/80-mkmini-network

# Layer 1: Ubuntu repository tools and host diagnostics. Keeping this separate
# means a transient ROS mirror failure does not redownload these packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg2 \
    lsb-release \
    software-properties-common \
    can-utils \
    git \
    iproute2 \
    iputils-ping \
    net-tools \
    vim \
    && add-apt-repository universe \
    && rm -rf /var/lib/apt/lists/*

# Layer 2: ROS repository plus the core ROS/build dependencies used by every
# workflow. curl retries cover transient proxy failures while fetching the key.
RUN curl --fail --show-error --location \
      --retry "${APT_RETRIES}" --retry-all-errors --retry-delay 2 \
      --connect-timeout 30 \
      https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
      -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] ${ROS2_APT_MIRROR} $(. /etc/os-release && echo ${UBUNTU_CODENAME}) main" \
      > /etc/apt/sources.list.d/ros2.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      python3-colcon-common-extensions \
      python3-pip \
      python3-pytest \
      python3-rosdep \
      python3-tk \
      python3-venv \
      python3-vcstool \
      ros-${ROS_DISTRO}-ackermann-msgs \
      ros-${ROS_DISTRO}-diagnostic-msgs \
      ros-${ROS_DISTRO}-pointcloud-to-laserscan \
      ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
      ros-${ROS_DISTRO}-ros-base \
    && rm -rf /var/lib/apt/lists/*

RUN rosdep init 2>/dev/null || true \
    && rosdep update

# livox_ros_driver2 does not declare Livox-SDK2 through rosdep. Install the
# official Mid-360S-compatible v1.3.1 release into /usr/local and verify that
# the release tag still resolves to the exact pinned commit.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

COPY Livox-SDK2-f5d9375f84efe2b15bc0a052d3e18482ed13adf4.tar.gz /tmp/Livox-SDK2.tar.gz

RUN echo "${LIVOX_SDK2_ARCHIVE_SHA256}  /tmp/Livox-SDK2.tar.gz" | sha256sum -c - \
    && mkdir -p /tmp/Livox-SDK2 \
    && tar -xzf /tmp/Livox-SDK2.tar.gz --strip-components=1 -C /tmp/Livox-SDK2 \
    && cmake -S /tmp/Livox-SDK2 -B /tmp/Livox-SDK2/build \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_CXX_FLAGS="-include cstdint" \
    && cmake --build /tmp/Livox-SDK2/build --parallel "$(nproc)" \
    && cmake --install /tmp/Livox-SDK2/build \
    && ldconfig \
    && test -f /usr/local/lib/liblivox_lidar_sdk_shared.so \
    && test -f /usr/local/include/livox_lidar_api.h \
    && rm -rf /tmp/Livox-SDK2 /tmp/Livox-SDK2.tar.gz

# ROS/Nav2 pulls Ubuntu's UCX/OpenMPI libraries into the system search path.
# NVIDIA's UCC library must resolve against the matching UCX shipped in HPC-X;
# otherwise importing Torch fails with an undefined ucs_config_doc_nop symbol.
# Keep this after the APT layers so the expensive dependency layers remain
# reusable when only the runtime linker policy changes.
ENV LD_LIBRARY_PATH=/opt/hpcx/ompi/lib:/opt/hpcx/ucx/lib:${LD_LIBRARY_PATH}

# Capture the exact Torch and CUDA build shipped by the pinned NVIDIA image.
# This does not require GPU access during docker build. Runtime GPU access is
# checked by run_mkmini_dev.sh before the interactive container starts.
RUN mkdir -p /etc/mkmini \
    && python3 -c 'import json, os, pathlib, torch; p=pathlib.Path("/etc/mkmini/thor-runtime.lock.json"); p.write_text(json.dumps({"schema_version": 1, "platform": "NVIDIA Thor JetPack 7.2 / L4T R39.2", "pytorch_base_image": os.environ["MKMINI_PYTORCH_BASE_IMAGE"], "livox_sdk2": {"repository": os.environ["MKMINI_LIVOX_SDK2_REPOSITORY"], "commit": os.environ["MKMINI_LIVOX_SDK2_COMMIT"]}, "torch": {"version": torch.__version__, "cuda_version": torch.version.cuda}}, indent=2) + "\n", encoding="utf-8")' \
    && python3 -c 'import torch; print(f"Torch {torch.__version__}; CUDA build {torch.version.cuda}")'

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python3 -c 'import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)'

WORKDIR /workspaces
CMD ["/bin/bash"]

# Optional target for a Nav2-based global planner. NeuPAN itself only consumes
# nav_msgs/Path on /plan; external planners do not need this target.
FROM neupan-core AS nav2-planner
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ros-${ROS_DISTRO}-nav2-costmap-2d \
      ros-${ROS_DISTRO}-nav2-lifecycle-manager \
      ros-${ROS_DISTRO}-nav2-map-server \
      ros-${ROS_DISTRO}-nav2-msgs \
      ros-${ROS_DISTRO}-nav2-navfn-planner \
      ros-${ROS_DISTRO}-nav2-planner \
      ros-${ROS_DISTRO}-nav2-smac-planner \
      ros-${ROS_DISTRO}-nav2-theta-star-planner \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -c 'import torch; print(f"Torch {torch.__version__}; CUDA build {torch.version.cuda}")'

# Optional complete debugging environment. It retains the previous Nav2,
# SLAM Toolbox and RViz behavior without making those dependencies mandatory
# for MK-mini NeuPAN reproduction.
FROM nav2-planner AS full-debug
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ros-${ROS_DISTRO}-nav2-bringup \
      ros-${ROS_DISTRO}-navigation2 \
      ros-${ROS_DISTRO}-rviz2 \
      ros-${ROS_DISTRO}-slam-toolbox \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -c 'import torch; print(f"Torch {torch.__version__}; CUDA build {torch.version.cuda}")'

# Default docker build target: the smallest environment required by NeuPAN,
# FAST-LIO, the scan pipeline and the MK-mini bridge.
FROM neupan-core AS dev
