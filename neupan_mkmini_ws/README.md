# NeuPAN 在宇合森 MK-mini 上的集成工作区

本工作区提供在阿克曼转向 MK-mini 上低速复现 NeuPAN 所需的集成层。当前设计把定位、可视化、二维避障输入和控制安全桥拆开，避免为了 RViz 看点云而改变 FAST-LIO 或 NeuPAN 的算法输入。

核心链路如下：

```text
MID-360 /livox/lidar CustomMsg -> FAST-LIO2 -> /Odometry 与 camera_init -> body TF
MID-360 /livox/lidar CustomMsg -> /livox/points PointCloud2 -> RViz 或 /scan
/livox/points -> /scan -> NeuPAN（SLAM/Global Planner 可选）
任意 Global Planner 或 Path Publisher /plan -> NeuPAN -> /neupan_cmd_vel -> /neupan/ackermann_cmd -> /ctrl_cmd
```

仓库不会直接包含上游项目源码。请使用 `scripts/import_upstreams.sh`；脚本优先导入 `mkmini_neupan.lock.repos`，缺失时才回退到 `mkmini_neupan.repos`，并将厂商提供的 `yhs_can_control` 与 `yhs_can_interfaces` 复制到 `src/`。

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
6. FAST_LIO 固定发布 `/Odometry` 和动态 `camera_init -> body`。底盘 `/odom` 仅作诊断，`publish_odom_tf` 必须为 false。
7. `config/fast_lio_tf.yaml` 默认为 `calibrated: false`；启用 `start_fast_lio_tf:=true` 时会故意失败，直到提供实测外参。

## Thor / ROS2 Jazzy 环境准备

在 Thor 上进入工作区后，先导入上游源码和厂商底盘包：

```bash
cd ~/workspaces/MK-mini_ws/neupan_mkmini_ws
bash scripts/import_upstreams.sh ~/workspaces/MK-mini_ws/ROS2_MK-mini/src
```

`import_upstreams.sh` 会从 `mkmini_neupan.repos` 导入 `neupan_ros2`、`livox_ros_driver2`、`FAST_LIO`、`NeuPAN`、`ir-sim` 等源码，冻结精确版本，并把 MK-mini 厂商包 `yhs_can_control` 与 `yhs_can_interfaces` 复制到 `src/`。如果厂商包路径不方便作为参数传入，也可以先设置：

```bash
export MKMINI_VENDOR_SRC=~/workspaces/MK-mini_ws/ROS2_MK-mini/src
bash scripts/import_upstreams.sh
```

然后安装 ROS 依赖、建立 Python venv、安装本地 `NeuPAN` 包并构建：

```bash
bash scripts/bootstrap_jazzy.sh --profile core
source install/setup.bash
```

`core` 是真机复现默认配置。需要 Nav2 global planner 时使用
`--profile nav2-planner`；需要完整 Nav2、SLAM Toolbox 和 RViz 调试环境时
使用 `--profile full-debug`。

Torch、CUDA 和 cuDNN 由 `docker/Dockerfile` 固定且已确认包含 `linux/arm64` 的 NVIDIA PyTorch 基础镜像提供，不在 venv 中安装或猜测普通 PyPI wheel。镜像构建时会读取：

```bash
python3 -c 'import torch; print(torch.__version__); print(torch.version.cuda)'
```

并自动写入镜像内的 `/etc/mkmini/thor-runtime.lock.json`。`run_mkmini_dev.sh` 将该路径通过 `MKMINI_THOR_RUNTIME_MANIFEST` 传给 bootstrap 和 preflight；文件缺失、版本不一致或 Torch 无法访问 GPU 时直接失败。仓库中的 `thor-runtime.lock.example.json` 仅说明格式，不作为运行时锁。其余 Python 包由 `requirements-thor.txt` 固定版本。

在 Thor 上启动容器后可确认：

```bash
python3 -c 'import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))'
cat /etc/mkmini/thor-runtime.lock.json
```

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

## 阶段 2：接入 `/scan`、外部 `/plan` 和安全桥

当 FAST-LIO 已在另一个终端运行时，`full_stack.launch.py` 不应重复启动 MID-360 driver。推荐让 `full_stack.launch.py start_scan_pipeline:=true` 负责 `/livox/lidar -> /livox/points -> /scan`，因此 FAST-LIO 终端建议关闭可视化旁路：

```bash
ros2 launch mkmini_neupan_bringup fast_lio_mid360.launch.py \
  start_mid360:=true \
  start_fast_lio:=true \
  start_visualization_cloud:=false \
  start_rviz:=false
```

另一个终端启动扫描转换和安全桥；`/plan` 由选定的 global planner 或
测试 path publisher 单独提供：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py \
  start_mid360:=false \
  start_visualization_cloud:=false \
  start_scan_pipeline:=true \
  start_slam:=false \
  start_navigation:=false \
  start_neupan:=false
```

这样可以避免两个节点同时发布 `/livox/points`。若只是调试 MID-360 driver，也可以单独运行：

```bash
ros2 launch mkmini_neupan_bringup mid360_driver.launch.py
ros2 launch mkmini_neupan_bringup full_stack.launch.py start_mid360:=true
```

## 阶段 3：启用 NeuPAN 闭环

NeuPAN 使用官方两层配置：`config/robots/mkmini/robot.yaml` 是 ROS 参数文件，`planner_config_file` 指向同目录 `planner.yaml`，`dune_checkpoint_file` 指向 Thor 可见的 checkpoint。任一文件不存在时 `neupan.launch.py` 会立即失败。

当前 checkpoint 位于 Thor 和容器均可见的稳定路径，`robot.yaml` 使用以下绝对路径：

```yaml
neupan_node:
  ros__parameters:
    planner_config_file: planner.yaml
    dune_checkpoint_file: /workspaces/MK-mini_ws/neupan_mkmini_ws/checkpoint/dune/model_5000.pth
```

该模型仍必须确认匹配 MK-mini 实车几何，并通过实车安全验证后才能用于闭环运行；替换模型时应保持该路径，或同步更新 `robot.yaml`。

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
  --neupan-config /workspaces/MK-mini_ws/neupan_mkmini_ws/src/mkmini_neupan_bringup/config/robots/mkmini/robot.yaml \
  fast_lio_tf_config:=/workspaces/MK-mini_ws/neupan_mkmini_ws/src/mkmini_neupan_bringup/config/fast_lio_tf.yaml \
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
  start_mid360:=true \
  start_fast_lio:=true \
  start_fast_lio_tf:=true \
  start_visualization_cloud:=false \
  start_scan_pipeline:=true
```

若使用现场专用 NeuPAN 配置，也在 preflight 中传入同一个配置：

```bash
ros2 run mkmini_neupan_bringup thor_neupan_preflight \
  --neupan-config /absolute/path/to/robot.yaml \
  start_scan_pipeline:=true
```

只有 preflight 最终输出 `RESULT  PASS` 后，再用相同参数启动 NeuPAN：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py \
  start_mid360:=true \
  start_fast_lio:=true \
  start_fast_lio_tf:=true \
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
  neupan_config:=/absolute/path/to/robot.yaml \
  fast_lio_tf_config:=/absolute/path/to/fast_lio_tf_site.yaml
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
