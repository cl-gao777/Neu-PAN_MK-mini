# NeuPAN ROS2 集成说明

## 为什么需要兼容适配器

社区 ROS2 wrapper 按以下方式发布阿克曼控制量：

- `Twist.linear.x`：速度，单位 m/s。
- `Twist.angular.z`：转向角，单位弧度。

这不符合标准 `cmd_vel` 的偏航角速度语义。若将它直接连接到 MK-mini 的
`cmd_vel_to_ctrl_cmd_node`，底盘适配器会再次计算转向角，导致控制错误。

因此，本工作区会立即将 `/neupan_cmd_vel` 转换为语义明确的
`/neupan/ackermann_cmd` `AckermannDriveStamped` 接口。只有安全桥可以将该命令
转换为 `/ctrl_cmd`。

## 上游必需配置

Thor 上启动 NeuPAN 前，应先导入并构建上游源码：

```bash
cd ~/workspaces/MK-mini_ws/neupan_mkmini_ws
bash scripts/import_upstreams.sh ~/workspaces/MK-mini_ws/ROS2_MK-mini/src
bash scripts/bootstrap_jazzy.sh
source install/setup.bash
```

`requirements-thor.txt` 只锁定普通 Python 依赖，不指定 PyTorch wheel。GPU Torch、CUDA 和 cuDNN 来自 `docker/Dockerfile` 固定且包含 `linux/arm64` 的 NVIDIA PyTorch 多架构基础镜像。镜像构建时自动把精确的 `torch.__version__`、`torch.version.cuda` 和基础镜像标签写入 `/etc/mkmini/thor-runtime.lock.json`；容器启动脚本通过 `MKMINI_THOR_RUNTIME_MANIFEST` 把该清单交给 bootstrap、独立 runtime 检查和 ROS preflight。缺失、空值或版本不匹配均失败关闭，仓库中的 `thor-runtime.lock.example.json` 仅作为格式示例。

为 MK-mini 配置 `neupan_ros2`：

- kinematics：`acker`
- wheelbase：`0.6`
- 最大速度：`0.6 m/s`（参考速度 `0.55 m/s`）
- 最大转向角：`0.436332 rad`（`25 deg`）
- 输入激光话题：`/scan`
- 输入路径话题：`/plan`
- TF：`map -> base_link`
- 输出话题：`/neupan_cmd_vel`

使用 `config/robots/mkmini/robot.yaml` 作为官方 ROS 参数入口，规划器参数位于同目录
`planner.yaml`。wrapper 只接收该 ROS 参数 YAML 和 `robot_config_dir`；不要传入旧的
`config_file`、`config_path` 或 `planner_config` 覆盖参数。
NeuPAN 安全桥把非零前进命令提升到最低可响应速度 `0.5 m/s`，并在 `0.6 m/s`
硬限幅；底盘 SDK 自带 `/cmd_vel` 适配器使用相同上限。NeuPAN 控制期间不能绕过安全桥。

当前仓库已包含并配置 DUNE checkpoint。该文件可用于启动和联调，但在确认模型匹配
MK-mini 实车几何并通过实车安全验证前，只能验证
`/neupan_cmd_vel -> /neupan/ackermann_cmd -> /ctrl_cmd` 的桥接和安全逻辑，以及
`/veh_diag_fb` 诊断新鲜度门控，不能进行 NeuPAN 实车闭环复现。模型几何应以
MK-mini 实车为准：`wheelbase=0.6`、`length=0.84-0.90`、`width=0.60`。

checkpoint 必须使用 Thor 运行时可见的绝对路径，例如：

```yaml
neupan_node:
  ros__parameters:
    planner_config_file: planner.yaml
    dune_checkpoint_file: /workspaces/MK-mini_ws/neupan_mkmini_ws/checkpoint/dune/model_5000.pth
```

NeuPAN 不直接消费 MID-360 点云。它需要 `/scan` `sensor_msgs/LaserScan` 和 `/plan`
`nav_msgs/Path`：

```text
/livox/lidar -> /livox/points -> /scan -> NeuPAN
Nav2 planner_server -> /plan -> NeuPAN
```

因此使用 MID-360 障碍物输入时，应打开 `full_stack.launch.py start_scan_pipeline:=true`。
若 FAST-LIO 已在独立终端启动 MID-360 driver，`full_stack.launch.py` 中应保持
`start_mid360:=false`，避免重复占用雷达 UDP 端口。

确认 checkpoint 匹配 MK-mini 几何并通过实车安全验证后，可显式启动 NeuPAN：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py \
  start_scan_pipeline:=true \
  start_neupan:=true
```

若 `neupan_ros2` 未通过锁文件导入并构建，或 planner/checkpoint 路径无效，
`neupan.launch.py` 会直接报错退出，避免进入没有算法输出的假闭环状态。

## 推荐的上游改进

对上游 wrapper 建立 fork 后，可在阿克曼模式下直接向 `/neupan/ackermann_cmd`
发布 `AckermannDriveStamped`。随后使用以下命令启动控制栈：

```bash
ros2 launch mkmini_neupan_bridge mkmini_neupan_control.launch.py \
  use_legacy_adapter:=false
```

直接 Ackermann 输出通过相同的架空轮和超时停车测试前，应继续保留兼容适配器。
无论采用哪种输出方式，都不得移除安全桥。
