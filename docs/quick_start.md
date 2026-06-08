# MK-mini 快速启动

本文档说明如何在 Thor 上位机上启动 MK-mini 底盘中间件。目标平台为
Ubuntu 24.04 + ROS 2 Jazzy。

## 1. 工作区结构

在 Thor 上请使用原生 Linux 文件系统，例如：

```bash
mkdir -p ~/ROS2_MK-mini/src
cd ~/ROS2_MK-mini
```

复制或克隆 SDK 后，目录结构应为：

```text
~/ROS2_MK-mini/
  src/
    yhs_can_control/
    yhs_can_interfaces/
  docs/
  README.md
```

不要在 Thor 上使用 `/mnt/e/...` 这类 Windows 挂载路径作为运行工作区。原生
Linux 路径可以避免时间戳、权限和符号链接问题。

## 2. 安装依赖

加载 Jazzy 环境并安装构建工具：

```bash
source /opt/ros/jazzy/setup.bash
sudo apt update
sudo apt install -y python3-colcon-common-extensions can-utils
rosdep update
rosdep install --from-paths src --ignore-src -r -y
```

本 SDK 使用的 ROS 包包括 `rclcpp`、`std_msgs`、`geometry_msgs`、`nav_msgs`、
`tf2`、`tf2_ros`，以及本地 `yhs_can_interfaces` 包。

## 3. 构建

在工作区根目录执行构建：

```bash
cd ~/ROS2_MK-mini
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

如果从 Windows 开发副本迁移到 Thor，复制前请删除旧的 `build/`、`install/`
和 `log/` 目录。

## 4. 配置 CAN

确认 CANH 和 CANL 连接正确后，以 500 kbit/s 启动 `can0`：

```bash
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up
ip -details link show can0
```

检查底盘是否正在发送 CAN 帧：

```bash
candump can0
```

如果 `can0` 不存在，请检查 CAN 适配器驱动、USB/PCI 设备状态，以及接口名称
是否不是 `can0`。

## 5. 启动 SDK

同时启动 CAN 桥接节点和 Nav2 `/cmd_vel` 适配节点：

```bash
cd ~/ROS2_MK-mini
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch yhs_can_control yhs_can_control.launch.py
```

该 launch 文件会启动：

- `yhs_can_control_node`：SocketCAN 桥接、反馈解析、`/odom` 和 TF。
- `cmd_vel_to_ctrl_cmd_node`：`/cmd_vel` 到 `/ctrl_cmd` 的适配器。

如需使用自定义参数文件：

```bash
ros2 launch yhs_can_control yhs_can_control.launch.py params_file:=/path/to/cfg.yaml
```

## 6. 基础检查

在另一个终端中执行：

```bash
source /opt/ros/jazzy/setup.bash
source ~/ROS2_MK-mini/install/setup.bash
ros2 topic list
ros2 topic echo /chassis_info_fb
ros2 topic echo /odom
ros2 topic hz /chassis_info_fb
```

如果 `publish_odom_tf` 为 true：

```bash
ros2 run tf2_ros tf2_echo odom base_link
```

## 7. 低速指令测试

首次运动测试时，请架空驱动轮或使用受控测试区域。默认适配器将速度限制为
`0.3 m/s`，转角限制为 `25 deg`，并禁用倒车。

发布一次短暂的前进指令：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
"{linear: {x: 0.05}, angular: {z: 0.0}}"
```

发布一次轻微转向指令：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
"{linear: {x: 0.05}, angular: {z: 0.1}}"
```

如果超过 `cmd_vel_timeout_sec` 没有新指令，适配器应持续发布零速度
`CtrlCmd` 消息。

## 8. Nav2 说明

ROS 2 Jazzy 的 Nav2 通常在 `/cmd_vel` 上使用 `geometry_msgs/msg/Twist`。
本 SDK 默认 `use_stamped_cmd_vel: false`。如果你的 Nav2 栈发布
`TwistStamped`，请设置：

```yaml
cmd_vel_to_ctrl_cmd_node:
  ros__parameters:
    use_stamped_cmd_vel: true
```

该适配器同一时间只能在 `/cmd_vel` 上使用一种消息类型。
