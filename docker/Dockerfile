# docker/Dockerfile
# Purpose: Base environment image for MK-mini NeuPAN development on NVIDIA Thor.
#
# Principle: Contains ONLY the environment (ROS 2 Jazzy + apt dependencies).
#            Source code is bind-mounted at container runtime — do NOT ADD or
#            COPY application code into this image.
#
# Build ON Thor (ARM64), NOT on Windows/x86_64:
#   cd ~/containers/mkmini_ws
#   docker build -t mkmini-jazzy:dev .

FROM ros:jazzy

ENV DEBIAN_FRONTEND=noninteractive
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Install system dependencies matching bootstrap_jazzy.sh.
# Dev tools (git, vim, ping, net-tools) are included for interactive use.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-venv \
    python3-vcstool \
    ros-jazzy-ackermann-msgs \
    ros-jazzy-diagnostic-msgs \
    ros-jazzy-nav2-bringup \
    ros-jazzy-navigation2 \
    ros-jazzy-pointcloud-to-laserscan \
    ros-jazzy-rmw-cyclonedds-cpp \
    ros-jazzy-slam-toolbox \
    can-utils \
    python3-pytest \
    git \
    vim \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Initialize rosdep (idempotent — base image may already have it)
RUN rosdep init 2>/dev/null || true \
    && rosdep update

WORKDIR /workspaces
CMD ["/bin/bash"]
