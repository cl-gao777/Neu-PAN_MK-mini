# Neu-PAN MK-mini / ROS 2 MK-mini 底盘 SDK

本仓库是面向 **宇合森 MK-mini** 底盘的 ROS 2 工作区，目标运行环境为 **Ubuntu 24.04 + ROS 2 Jazzy**。项目保留厂商 ROS 2 包名和消息接口，并补充了 MK-mini 在导航、底盘反馈、里程计和实车测试中需要的工程化封装。

> 注意：仓库名为 `Neu-PAN_MK-mini`，但本目录本身是 MK-mini 底盘 ROS 2 SDK。它可以作为 NeuPAN 集成链路中的底盘驱动层使用；NeuPAN 到底盘的安全桥接可在上层工作区中接入本仓库提供的 `/ctrl_cmd`、`/chassis_info_fb`、`/odom` 等接口。

## 项目做了什么

本项目提供两个 ROS 2 包：

| 包名 | 作用 |
| --- | --- |
| `yhs_can_interfaces` | 定义 MK-mini 底盘相关自定义消息，例如 `CtrlCmd`、`ChassisInfoFb`、`OdoFb`、`VehDiagFb` 等。 |
| `yhs_can_control` | 通过 SocketCAN 连接底盘 CAN 总线，解析底盘反馈，发布里程计和 TF，并提供 `/cmd_vel` 到 `/ctrl_cmd` 的适配节点。 |

核心能力：

- 通过 `can0` 与 MK-mini 底盘通信。
- 将底盘 CAN 反馈解析为 ROS 2 话题。
- 发布 `/odom` 里程计和 `odom -> base_link` TF。
- 提供 `cmd_vel_to_ctrl_cmd_node`，把 Nav2 或其他上层控制器的 `/cmd_vel` 转为 MK-mini 底盘控制命令 `/ctrl_cmd`。
- 提供 `odom_distance_test_node`，用于低速直线行驶并验证里程计距离误差。
- 提供 C++ gtest 单元测试，覆盖 CAN 协议解析和里程计距离测试逻辑。
- 提供实车启动、话题参数、里程计精度测试和安全检查文档。

## 目录结构

```text
.
├── docs/
│   ├── quick_start.md
│   ├── thor_mkmini_control_plan.md
│   ├── odom_accuracy_test_plan.md
│   ├── topics_and_params.md
│   ├── bringup_checklist.md
│   └── official_usage_notes.md
├── src/
│   ├── yhs_can_interfaces/
│   └── yhs_can_control/
├── .gitignore
└── README.md
```

`build/`、`install/`、`log/` 是 colcon 生成目录，不进入版本库。

## 环境要求

- Ubuntu 24.04
- ROS 2 Jazzy
- SocketCAN 工具链
- 一路可用 CAN 设备，默认接口名为 `can0`
- MK-mini 底盘及其 CAN 线束

推荐在原生 Linux 路径下运行，例如：

```bash
~/ROS2_MK-mini
```

不要把 `/mnt/e/...` 这类 Windows 挂载路径作为正式运行目录，ROS 2 构建、符号链接、权限和实时性都更容易出问题。

## 安装依赖

```bash
cd ~/ROS2_MK-mini
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
```

## 构建

```bash
cd ~/ROS2_MK-mini
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

只构建底盘相关包：

```bash
colcon build --symlink-install \
  --packages-select yhs_can_interfaces yhs_can_control
source install/setup.bash
```

## 配置 CAN

默认使用 `can0`，波特率为 `500000`：

```bash
sudo ip link set can0 down || true
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up
```

检查 CAN 总线是否有数据：

```bash
candump can0
```

如果 `candump` 没有任何输出，需要先检查底盘供电、CAN 线束、终端电阻、接口名和波特率。

## 启动底盘 SDK

默认启动文件：

```bash
ros2 launch yhs_can_control yhs_can_control.launch.py
```

该 launch 会启动两个节点：

| 节点 | 功能 |
| --- | --- |
| `yhs_can_control_node` | 连接 CAN，总线收发，发布底盘反馈、里程计和 TF。 |
| `cmd_vel_to_ctrl_cmd_node` | 订阅 `/cmd_vel`，转换并发布 `/ctrl_cmd`。 |

使用自定义参数文件：

```bash
ros2 launch yhs_can_control yhs_can_control.launch.py \
  params_file:=/absolute/path/to/cfg.yaml
```

默认参数文件位于：

```text
src/yhs_can_control/params/cfg.yaml
```

## 常用话题

| 话题 | 方向 | 说明 |
| --- | --- | --- |
| `/cmd_vel` | 输入 | 上层导航或控制器输出的速度指令，类型通常为 `geometry_msgs/msg/Twist`。 |
| `/ctrl_cmd` | 输出到底盘 | MK-mini 底盘控制命令，类型为 `yhs_can_interfaces/msg/CtrlCmd`。 |
| `/chassis_info_fb` | 底盘反馈 | 底盘状态、故障、车速、电池、诊断等综合反馈。 |
| `/odom` | 输出 | 里程计，供 Nav2 或上层定位导航使用。 |
| `odom -> base_link` | TF | 底盘里程计坐标变换。 |

查看话题：

```bash
ros2 topic list
ros2 topic echo /chassis_info_fb
ros2 topic echo /odom
ros2 run tf2_ros tf2_echo odom base_link
```

## 发送控制命令

### 推荐方式：发布 `/cmd_vel`

启动 SDK 后，可以用低速命令做架空轮测试：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.05}, angular: {z: 0.0}}"
```

停止：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.0}}"
```

### 直接发布 `/ctrl_cmd`

只有在明确知道 MK-mini 控制字段含义时才建议直接发 `/ctrl_cmd`。正常导航链路建议从 `/cmd_vel` 进入，由适配节点转换。

## Nav2 / NeuPAN 集成方式

本仓库负责底盘 SDK 层，典型链路为：

```text
Nav2 或 NeuPAN 上层控制器
  -> /cmd_vel 或上层安全桥输出
  -> cmd_vel_to_ctrl_cmd_node 或安全桥
  -> /ctrl_cmd
  -> yhs_can_control_node
  -> CAN 总线
  -> MK-mini 底盘
```

如果接入 NeuPAN，建议在上层增加安全桥，显式处理解锁、急停、反馈超时、定位超时、速度限幅和转角限幅，再输出 `/ctrl_cmd`。

## 里程计精度测试

构建后可以运行：

```bash
ros2 run yhs_can_control odom_distance_test_node --ros-args \
  -p armed:=true \
  -p target_distance_m:=1.0 \
  -p target_speed_mps:=0.05
```

该节点会：

1. 发布低速直线控制命令。
2. 读取 `/odom`。
3. 到达目标里程后自动停车。
4. 输出测试结果。

注意：里程计精度不能只看 `/odom` 是否到达目标值，必须用卷尺、地面标线或外部定位系统测量真实行驶距离，再计算误差。

详细流程见：

```text
docs/odom_accuracy_test_plan.md
```

## 运行测试

本仓库包含 C++ gtest：

- `src/yhs_can_control/test/test_mk_mini_protocol.cpp`
- `src/yhs_can_control/test/test_odom_distance_test_logic.cpp`

运行测试：

```bash
cd ~/ROS2_MK-mini
source /opt/ros/jazzy/setup.bash
colcon test --packages-select yhs_can_interfaces yhs_can_control
colcon test-result --verbose
```

如果只想重新构建并测试底盘控制包：

```bash
colcon build --symlink-install --packages-select yhs_can_control
colcon test --packages-select yhs_can_control
colcon test-result --verbose
```

## 实车安全注意事项

首次测试必须满足：

- 车辆架空或处在受控低速测试区。
- 有物理急停或遥控器接管能力。
- CAN 线束、供电和终端电阻确认无误。
- 初始速度限制在低速，例如 `0.05 m/s`。
- 先确认 `/chassis_info_fb`、`/odom` 和 TF 正常，再发送运动命令。

任何异常都应立即发送零速度命令，并使用物理急停或遥控器接管。

## 推荐阅读顺序

1. `docs/quick_start.md`：构建、CAN 配置、启动和首次检查。
2. `docs/thor_mkmini_control_plan.md`：Thor 上位机连接并控制 MK-mini 的流程。
3. `docs/odom_accuracy_test_plan.md`：里程计精度测试方法。
4. `docs/topics_and_params.md`：话题、消息和参数说明。
5. `docs/bringup_checklist.md`：分阶段实车启动和安全检查清单。
6. `docs/official_usage_notes.md`：厂商使用说明中的关键信息摘录。

## 常见问题

### 启动后底盘不动

检查顺序：

1. `can0` 是否存在并已 `UP`。
2. `candump can0` 是否能看到底盘 CAN 帧。
3. `/chassis_info_fb` 是否有数据。
4. `/cmd_vel` 是否有发布。
5. `/ctrl_cmd` 是否由适配节点输出。
6. 底盘是否处于允许控制的档位和模式。

### 有 `/cmd_vel` 但没有 `/ctrl_cmd`

检查 `cmd_vel_to_ctrl_cmd_node` 是否启动：

```bash
ros2 node list
ros2 node info /cmd_vel_to_ctrl_cmd_node
```

检查参数文件是否正确加载。

### 有 `/ctrl_cmd` 但车不动

检查底盘反馈中的故障位、急停状态、控制模式、线控使能状态和 CAN 通信状态。

## 许可证

当前 `package.xml` 中的许可证字段仍为待补充状态。正式公开发布或商用前，需要确认厂商 SDK、DBC 文件和本仓库新增代码的许可证声明。
