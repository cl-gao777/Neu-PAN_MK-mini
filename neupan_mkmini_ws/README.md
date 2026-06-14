# NeuPAN 在宇合森 MK-mini 上的集成工作区

本工作区提供在阿克曼转向 MK-mini 上低速复现 NeuPAN 所需的集成层：

`Mid-360 CustomMsg -> FAST-LIO2`，同时通过
`CustomMsg -> /livox/points -> /scan -> slam_toolbox -> Nav2 全局路径 -> NeuPAN -> Ackermann 安全桥 -> MK-mini`

仓库不会直接包含上游项目源码。请使用 `mkmini_neupan.repos` 导入依赖，并将现有
`yhs_can_control` 与 `yhs_can_interfaces` 包复制到 `src/`。

## 已实现内容

- 在 NeuPAN 与底盘之间建立明确的 `AckermannDriveStamped` 接口。
- 提供上游 ROS2 wrapper 兼容适配器；该 wrapper 在阿克曼模式下使用
  `Twist.angular.z` 表示转向角，而不是偏航角速度。
- 提供失效安全的 `/ctrl_cmd` 桥，包括软件解锁、软件急停、命令超时、
  整车诊断反馈超时、故障门控、速度/转角限幅，以及正确的 MK-mini 档位
  （`D=4`、`R=2`）。
- 提供可独立启动的在线 SLAM、Nav2 与底盘控制 launch 文件。
- 提供 MK-mini 几何、点云切片、SLAM Toolbox 与 Nav2 配置。
- 提供安全、标定、接口约定和验收手册。

## 关键安全规则

1. 禁止将 `/neupan_cmd_vel` 连接到厂商的 `cmd_vel_to_ctrl_cmd_node`。
2. NeuPAN 控制期间禁止启动厂商的 `yhs_can_control.launch.py`，因为它会同时启动存在冲突的 cmd_vel 适配器。
3. 安全桥启动后默认未解锁；在收到 `/veh_diag_fb` 健康整车诊断反馈和明确的解锁消息前，只发布零速度命令。
4. 每次真机运动测试必须保留遥控器、物理急停和独立安全员。
5. 正式配置会监控 `map -> base_link`；TF 缺失、过期或时间异常时，安全桥会停车。

## Thor / ROS2 Jazzy 环境准备

```bash
cd ~/neupan_mkmini_ws
vcs import . < mkmini_neupan.repos
bash scripts/freeze_revisions.sh

# Copy the two local MK-mini driver packages supplied with the robot.
cp -a /path/to/ROS2_MK-mini/src/yhs_can_control src/
cp -a /path/to/ROS2_MK-mini/src/yhs_can_interfaces src/

bash scripts/bootstrap_jazzy.sh
source install/setup.bash
```

优先构建底盘驱动和本工作区的集成包：

```bash
colcon build --symlink-install \
  --packages-select yhs_can_interfaces yhs_can_control \
  mkmini_neupan_bridge mkmini_neupan_bringup
```

任何装有 Python 3 的主机都可以运行纯安全逻辑测试：

```bash
python3 -m pytest

# Windows local development:
.venv\Scripts\python.exe -m pytest
```

## 启动顺序

首先启动外部硬件与定位组件：

1. 启动 Mid-360 的 `livox_ros_driver2`。本仓库提供了保持 CustomMsg 输出的封装：
   `ros2 launch mkmini_neupan_bringup mid360_driver.launch.py`。
2. 使用实测的 LiDAR 到 IMU/`base_link` 外参启动 FAST-LIO2。
3. 使用针对 MK-mini 外形训练的 DUNE checkpoint 启动 NeuPAN ROS2。

然后启动底盘、感知、SLAM、Nav2 与安全桥集成栈：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py
```

`full_stack.launch.py` 默认不启动 Mid-360、FAST-LIO2 和 NeuPAN，避免抢占雷达 UDP 端口或使用未经验证的
外参和 DUNE checkpoint。确认 MID-360 使用 `192.168.1.3`、Thor 网口使用 `192.168.1.50/24` 后，
可以显式打开本仓库的 MID-360 driver：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py start_mid360:=true
```

训练并替换 MK-mini DUNE checkpoint 后，
才允许显式打开 NeuPAN：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py start_neupan:=true
```

如需使用现场专用 NeuPAN 配置，可在全栈 launch 中显式传入：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py \
  start_neupan:=true \
  neupan_config:=/absolute/path/to/neupan_mkmini.yaml
```

如果 `config/neupan_mkmini.yaml` 仍包含
`REPLACE_WITH_TRAINED_MKMINI_DUNE_CHECKPOINT`，NeuPAN launch 会立即失败。请先按
MK-mini 几何参数训练 DUNE：`wheelbase=0.6`、`length=0.84-0.90`、`width=0.60`，
然后把 `dune_checkpoint` 替换为训练好的 checkpoint 绝对路径。

完成架空轮安全检查后，使用以下命令解锁：

```bash
bash scripts/arm_bridge.sh I_HAVE_REMOTE_AND_ESTOP
```

架空轮阶段尚未建立定位 TF 时，只能显式使用低速架空轮配置：

```bash
ros2 launch mkmini_neupan_bridge mkmini_neupan_control.launch.py \
  bridge_params:=/absolute/path/to/safety_bridge_bench.yaml
```

该配置禁止用于落地导航测试。

开始真机工作前，请阅读 [真机安全检查表](docs/safety-checklist.md) 和
[验收测试](docs/acceptance-test.md)。
上游项目及其用途见 [项目与论文索引](docs/research-index.md)。
