# Neu-PAN MK-mini

本仓库是面向宇合森 MK-mini 底盘的父级仓库，组织底盘 ROS 2 SDK、NeuPAN 集成工作区和 Docker/Thor 真机运行脚本。根目录只做项目导航和真机入口索引；不要在根目录直接执行 colcon build。

当前推荐的真机入口是在 Thor 宿主机运行：

```bash
cd ~/workspaces/MK-mini_ws
bash docker/start_real_robot_neupan.sh --dry-run
bash docker/start_real_robot_neupan.sh
```

脚本会先做宿主机侧 workspace、Docker 镜像、CAN 和 LiDAR 基本检查，再进入或复用容器，在容器内运行 Thor preflight。只有 `ros2 run mkmini_neupan_bringup thor_neupan_preflight` 通过后，才会启动 `full_stack.launch.py start_neupan:=true`。

## 目录结构

```text
.
├── ROS2_MK-mini/
│   ├── docs/
│   ├── src/yhs_can_control/
│   └── src/yhs_can_interfaces/
├── docker/
│   ├── Dockerfile
│   ├── run_mkmini_dev.sh
│   └── start_real_robot_neupan.sh
├── neupan_mkmini_ws/
│   ├── docs/
│   ├── scripts/
│   └── src/
├── LICENSE
├── README.md
└── .gitignore
```

## 子项目职责

| 路径 | 作用 |
| --- | --- |
| [`ROS2_MK-mini/`](ROS2_MK-mini/) | MK-mini 底盘 ROS 2 SDK，包含厂商消息接口、SocketCAN 底盘控制、里程计、TF 和实车测试文档。 |
| [`neupan_mkmini_ws/`](neupan_mkmini_ws/) | NeuPAN 到 MK-mini 的集成工作区，包含 Ackermann 安全桥、MID-360/FAST-LIO/SLAM/Nav2/NeuPAN bringup、preflight、验收脚本和安全文档。 |
| [`docker/`](docker/) | Thor 上的 ROS 2 Jazzy 开发镜像、容器入口、底盘/NeuPAN 构建脚本，以及宿主机真机一键启动入口。 |

## 推荐阅读顺序

1. 本文件：确认仓库结构、真机入口和禁止事项。
2. [`docker/README.md`](docker/README.md)：构建 Thor Docker 镜像、进入容器、宿主机/容器责任划分和真机一键启动。
3. [`neupan_mkmini_ws/README.md`](neupan_mkmini_ws/README.md)：NeuPAN 集成链路、checkpoint、preflight、full stack launch 和验收流程。
4. [`neupan_mkmini_ws/docs/safety-checklist.md`](neupan_mkmini_ws/docs/safety-checklist.md)：每次真机测试前必须执行的安全检查。
5. [`ROS2_MK-mini/README.md`](ROS2_MK-mini/README.md)：底盘 SDK 构建、CAN、话题、里程计和厂商适配器说明。

## 真机启动主路径

### 1. 宿主机准备

在 Thor 宿主机上完成 Docker 镜像、CAN 和 LiDAR 网络准备。详细命令见 [`docker/README.md`](docker/README.md)。

```bash
cd ~/workspaces/MK-mini_ws/docker
docker build -t mkmini-jazzy:dev .
```

CAN、LiDAR 和 Docker 都准备好后，回到仓库根目录先看 dry-run：

```bash
cd ~/workspaces/MK-mini_ws
bash docker/start_real_robot_neupan.sh --dry-run
```

### 2. Preflight 通过后再启动 NeuPAN

正式一键启动命令仍从 Thor 宿主机运行：

```bash
bash docker/start_real_robot_neupan.sh
```

这个入口会在容器内运行：

```bash
ros2 run mkmini_neupan_bringup thor_neupan_preflight
```

preflight 会检查 Python 运行时、MK-mini 的 `robot.yaml` / `planner.yaml` 配置与 DUNE checkpoint、关键 ROS topic 和频率、`cmd_vel_to_ctrl_cmd_node` 冲突、`/ctrl_cmd` 发布者数量，以及 `map -> base_link` TF。最终输出 `RESULT  PASS` 后，脚本才进入正式启动：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py start_neupan:=true
```

如果已经在容器内，可直接使用容器 runner：

```bash
bash scripts/start_real_robot_neupan.sh --dry-run
bash scripts/start_real_robot_neupan.sh
```

## 真机安全顺序

每次真机运行前必须按这个顺序走：

1. 确认已配置的 MK-mini DUNE checkpoint 文件存在、匹配实车几何，并已通过实车安全验证。
2. 运行 `bash docker/start_real_robot_neupan.sh --dry-run`，确认 workspace、镜像、CAN、LiDAR 和 launch 参数符合现场配置。
3. 运行 Thor preflight，并确认最终输出 `RESULT  PASS`。
4. 人工确认遥控接管、物理急停、独立安全员和测试区域隔离。
5. 启动正式栈后，再手动执行安全桥解锁命令。

一键脚本不会自动解锁安全桥，不会运行 `scripts/arm_bridge.sh`，也不会发布运动命令；Ctrl+C 或退出时会 best-effort 执行 `scripts/disarm_bridge.sh`。

## 明确禁止

- 不要在根目录直接执行 colcon build；请分别在 `ROS2_MK-mini/`、`neupan_mkmini_ws/` 或容器脚本中构建。
- 不要跳过 `thor_neupan_preflight` 直接运行 `full_stack.launch.py start_neupan:=true`。
- NeuPAN 控制期间不要启动厂商 `cmd_vel_to_ctrl_cmd_node`，也不要启动会带出该节点的厂商 `yhs_can_control.launch.py`。
- 不要让 `/ctrl_cmd` 出现多个发布者；NeuPAN 控制期间应只有安全桥发布 `/ctrl_cmd`。
- 不要让脚本自动 arm、unlock 或直接发布运动命令。

## 常用命令速查

| 场景 | 命令 |
| --- | --- |
| 在 Thor 上构建 Docker 镜像 | `cd ~/workspaces/MK-mini_ws/docker && docker build -t mkmini-jazzy:dev .` |
| 进入开发容器 | `cd ~/workspaces/MK-mini_ws/docker && bash run_mkmini_dev.sh` |
| 宿主机真机一键 dry-run | `cd ~/workspaces/MK-mini_ws && bash docker/start_real_robot_neupan.sh --dry-run` |
| 宿主机真机一键启动 | `cd ~/workspaces/MK-mini_ws && bash docker/start_real_robot_neupan.sh` |
| 容器内 runner dry-run | `cd /workspaces/MK-mini_ws/neupan_mkmini_ws && bash scripts/start_real_robot_neupan.sh --dry-run` |
| 容器内直接跑 preflight | `ros2 run mkmini_neupan_bringup thor_neupan_preflight` |
| 手动启动 NeuPAN full stack | `ros2 launch mkmini_neupan_bringup full_stack.launch.py start_neupan:=true` |
| 本地纯 Python 测试 | `cd neupan_mkmini_ws && .venv\Scripts\python.exe -m pytest` |
| 容器内测试合集 | `bash /workspaces/MK-mini_ws/docker/scripts/run_tests.sh` |

## 手动开发路径

底盘 SDK 构建：

```bash
cd ~/workspaces/MK-mini_ws/ROS2_MK-mini
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

NeuPAN workspace 初始化和构建：

```bash
cd ~/workspaces/MK-mini_ws/neupan_mkmini_ws
bash scripts/import_upstreams.sh ~/workspaces/MK-mini_ws/ROS2_MK-mini/src
bash scripts/bootstrap_jazzy.sh
source install/setup.bash
```

优先只构建底盘接口和 NeuPAN 集成包：

```bash
colcon build --symlink-install \
  --packages-select yhs_can_interfaces yhs_can_control \
  mkmini_neupan_bridge mkmini_neupan_bringup
```

## 版本库约定

- `build/`、`install/`、`log/`、`.venv/`、`.api_tmp/` 和本地 Git 备份目录不进入版本库。
- 上游源码通过 `neupan_mkmini_ws/mkmini_neupan.repos` 和 `scripts/import_upstreams.sh` 导入，不直接烤进 Docker 镜像。
- Docker 镜像只放环境，代码通过 bind mount 挂入容器；改代码不需要重建镜像。
