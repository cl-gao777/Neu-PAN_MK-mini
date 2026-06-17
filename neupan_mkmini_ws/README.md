# NeuPAN 在宇合森 MK-mini 上的集成工作区

本工作区提供在阿克曼转向 MK-mini 上低速复现 NeuPAN 所需的集成层。当前设计把定位、可视化、二维避障输入和控制安全桥拆开，避免为了 RViz 看点云而改变 FAST-LIO 或 NeuPAN 的算法输入。

核心链路如下：

```text
MID-360 /livox/lidar CustomMsg -> FAST-LIO2 -> /odom 与 TF
MID-360 /livox/lidar CustomMsg -> /livox/points PointCloud2 -> RViz 或 /scan
/livox/points -> /scan -> SLAM Toolbox / Nav2 / NeuPAN
Nav2 /plan -> NeuPAN -> /neupan_cmd_vel -> /neupan/ackermann_cmd -> /ctrl_cmd
```

仓库不会直接包含上游项目源码。请使用 `scripts/import_upstreams.sh` 导入 `mkmini_neupan.repos` 中声明的依赖，并将厂商提供的 `yhs_can_control` 与 `yhs_can_interfaces` 复制到 `src/`。

## 已实现内容

- 在 NeuPAN 与底盘之间建立明确的 `AckermannDriveStamped` 接口。
- 提供上游 ROS2 wrapper 兼容适配器；该 wrapper 在阿克曼模式下使用 `Twist.angular.z` 表示转向角，而不是偏航角速度。
- 提供失效安全的 `/ctrl_cmd` 桥，包括软件解锁、软件急停、命令超时、整车诊断反馈超时、故障门控、速度/转角限幅，以及正确的 MK-mini 档位（`D=4`、`R=2`）。
- 提供 MID-360 CustomMsg 驱动封装、FAST-LIO 启动封装、RViz 点云显示模板，以及 `/livox/lidar -> /livox/points` 可视化/扫描旁路。
- 提供在线 SLAM、Nav2、NeuPAN 和底盘控制的集成 launch 文件。
- 提供 MK-mini 几何、点云切片、SLAM Toolbox、Nav2、安全、标定、接口约定和验收文档。

## 关键安全规则

1. 禁止将 `/neupan_cmd_vel` 连接到厂商的 `cmd_vel_to_ctrl_cmd_node`。
2. NeuPAN 控制期间禁止启动厂商的 `yhs_can_control.launch.py`，因为它会同时启动存在冲突的 cmd_vel 适配器。
3. 安全桥启动后默认未解锁；在收到 `/veh_diag_fb` 健康整车诊断反馈和明确的解锁消息前，只发布零速度命令。
4. 每次真机运动测试必须保留遥控器、物理急停和独立安全员。
5. 正式配置会监控 `map -> base_link`；TF 缺失、过期或时间异常时，安全桥会停车。
6. 真机运动前必须选定唯一的 `odom -> base_link` 发布者；FAST-LIO2 与底盘驱动不能同时发布该 TF。

## Thor / ROS2 Jazzy 环境准备

在 Thor 上进入工作区后，先导入上游源码和厂商底盘包：

```bash
cd ~/neupan_mkmini_ws
bash scripts/import_upstreams.sh /path/to/ROS2_MK-mini/src
```

`import_upstreams.sh` 会从 `mkmini_neupan.repos` 导入 `neupan_ros2`、`livox_ros_driver2`、`FAST_LIO`、`NeuPAN`、`ir-sim` 等源码，冻结精确版本，并把 MK-mini 厂商包 `yhs_can_control` 与 `yhs_can_interfaces` 复制到 `src/`。如果厂商包路径不方便作为参数传入，也可以先设置：

```bash
export MKMINI_VENDOR_SRC=/path/to/ROS2_MK-mini/src
bash scripts/import_upstreams.sh
```

然后安装 ROS 依赖、建立 Python venv、安装本地 `NeuPAN` 包并构建：

```bash
bash scripts/bootstrap_jazzy.sh
source install/setup.bash
```

如果 `bootstrap_jazzy.sh` 报 `torch` 缺失，请先安装 NVIDIA/Thor 兼容的 PyTorch。若缺少 `cvxpy` 或 `cvxpylayers`，在 `.venv` 中补齐后重新运行 `python3 scripts/check_neupan_runtime.py`。

优先构建底盘驱动和本工作区的集成包时，可使用：

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

## 阶段 1：仅启动 MID-360、FAST-LIO 和 RViz 点云观察

确认 MID-360 使用 `192.168.1.3`，Thor 网口 `enP2p1s0` 使用 `192.168.1.50/24`：

```bash
sudo ip addr add 192.168.1.50/24 dev enP2p1s0
ping 192.168.1.3
```

启动 FAST-LIO，并打开 `/livox/lidar -> /livox/points` 可视化旁路：

```bash
ros2 launch mkmini_neupan_bringup fast_lio_mid360.launch.py \
  start_mid360:=true \
  start_fast_lio:=true \
  start_visualization_cloud:=true \
  start_rviz:=false
```

如果 Thor 已配置 GUI、X11 或 Wayland 转发，可把 `start_rviz:=true`；也可以单独启动：

```bash
ros2 launch mkmini_neupan_bringup mid360_rviz.launch.py
```

这个阶段只用于确认 MID-360、FAST-LIO 和 RViz 点云显示。它不会启动 `/scan`、SLAM Toolbox、Nav2 或 NeuPAN。

## 阶段 2：接入 `/scan`、Nav2 和安全桥

当 FAST-LIO 已在另一个终端运行时，`full_stack.launch.py` 不应重复启动 MID-360 driver。推荐让 `full_stack.launch.py start_scan_pipeline:=true` 负责 `/livox/lidar -> /livox/points -> /scan`，因此 FAST-LIO 终端建议关闭可视化旁路：

```bash
ros2 launch mkmini_neupan_bringup fast_lio_mid360.launch.py \
  start_mid360:=true \
  start_fast_lio:=true \
  start_visualization_cloud:=false \
  start_rviz:=false
```

另一个终端启动感知、SLAM、Nav2 和安全桥：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py \
  start_mid360:=false \
  start_visualization_cloud:=false \
  start_scan_pipeline:=true \
  start_neupan:=false
```

这样可以避免两个节点同时发布 `/livox/points`。若只是调试 MID-360 driver，也可以单独运行：

```bash
ros2 launch mkmini_neupan_bringup mid360_driver.launch.py
ros2 launch mkmini_neupan_bringup full_stack.launch.py start_mid360:=true
```

## 阶段 3：启用 NeuPAN 闭环

训练并替换 MK-mini DUNE checkpoint 后，才允许显式打开 NeuPAN。`config/neupan_mkmini.yaml` 中若仍包含 `REPLACE_WITH_TRAINED_MKMINI_DUNE_CHECKPOINT`，`neupan.launch.py` 会立即失败，避免进入没有算法输出的假闭环状态。

推荐把 checkpoint 放在 Thor 可见的稳定路径，并在配置中使用绝对路径，例如：

```yaml
pan:
  dune_checkpoint: /workspaces/MK-mini_ws/neupan_mkmini_ws/checkpoints/dune/model_5000.pth
```

真机上推荐使用宿主机一键入口：

```bash
cd ~/workspaces/MK-mini_ws
bash docker/start_real_robot_neupan.sh --dry-run
bash docker/start_real_robot_neupan.sh
```

该入口会在宿主机检查 workspace、Docker 镜像、CAN 与 LiDAR 基本状态，然后进入或复用 `mkmini-dev` 容器，在容器内运行 Thor preflight；preflight 通过后才自动启动 `full_stack.launch.py start_neupan:=true`。如果已经在容器内执行同一个 `docker/start_real_robot_neupan.sh`，脚本会直接转发到容器内 runner，不会递归启动 Docker。

容器内也可以直接 dry-run 或运行 runner：

```bash
bash scripts/start_real_robot_neupan.sh --dry-run
bash scripts/start_real_robot_neupan.sh
```

需要现场参数时，一键脚本和正式 launch 使用同一组参数；`start_neupan:=...` 会被 runner 忽略，preflight 固定为 false，正式启动固定为 true：

```bash
bash docker/start_real_robot_neupan.sh \
  --neupan-config /workspaces/MK-mini_ws/neupan_mkmini_ws/config/neupan_site.yaml \
  start_mid360:=true \
  start_scan_pipeline:=true
```

一键脚本不会自动解锁安全桥，不会运行 `scripts/arm_bridge.sh`，也不会发布运动命令；Ctrl+C 或退出时会 best-effort 执行 `scripts/disarm_bridge.sh`。

启动 NeuPAN 前，先运行 Thor preflight。该命令会自动拉起
`full_stack.launch.py start_neupan:=false` 的前置栈，检查 Python 运行时、
MK-mini DUNE checkpoint、关键话题与频率、`cmd_vel_to_ctrl_cmd_node` 冲突、
`/ctrl_cmd` 发布者数量，以及 `map -> base_link` TF；检查结束后会关闭前置栈。

preflight 使用的 launch 参数应与正式启动保持一致，只是不要传入
`start_neupan:=true`：

```bash
ros2 run mkmini_neupan_bringup thor_neupan_preflight \
  start_mid360:=false \
  start_visualization_cloud:=false \
  start_scan_pipeline:=true
```

若使用现场专用 NeuPAN 配置，也在 preflight 中传入同一个配置：

```bash
ros2 run mkmini_neupan_bringup thor_neupan_preflight \
  --neupan-config /absolute/path/to/neupan_mkmini.yaml \
  start_scan_pipeline:=true
```

只有 preflight 最终输出 `RESULT  PASS` 后，再用相同参数启动 NeuPAN：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py \
  start_mid360:=false \
  start_visualization_cloud:=false \
  start_scan_pipeline:=true \
  start_neupan:=true
```

NeuPAN 启动后，再验收算法输出频率：

```bash
ros2 topic hz /neupan_cmd_vel
ros2 topic hz /neupan/ackermann_cmd
```

如需使用现场专用 NeuPAN 配置，可显式传入：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py \
  start_scan_pipeline:=true \
  start_neupan:=true \
  neupan_config:=/absolute/path/to/neupan_mkmini.yaml
```

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

开始真机工作前，请阅读 [真机安全检查表](docs/safety-checklist.md)、[验收测试](docs/acceptance-test.md)、[MID-360 + FAST-LIO + RViz](docs/mid360-fast-lio-rviz.md) 和 [接口约定](docs/interface-contract.md)。上游项目及其用途见 [项目与论文索引](docs/research-index.md)。
