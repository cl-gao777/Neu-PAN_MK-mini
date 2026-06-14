# Docker 环境：MK-mini NeuPAN 开发（NVIDIA Thor）

## 1. 设计原则

**镜像只放环境，不烤代码。**

- `Dockerfile` 只装 ROS 2 Jazzy + apt 系统依赖 + 开发工具，不对仓库文件做 `ADD`/`COPY`
- 代码在运行时通过 `-v` bind mount 挂入容器
- 改代码不需要重新构建镜像
- 所有 `docker/scripts/` 下的脚本已内置容器路径翻译，无需手动记路径

## 2. 前提条件

### Thor 上（宿主机）

- Docker Engine 已安装，你的用户已加入 `docker` 组
- Thor 为 ARM64 架构（`uname -m` 输出 `aarch64`）
- （可选）`nvidia-container-toolkit` — 需要 GPU 加速时用到

### 你的开发机上（Windows）

- Git（版本控制）
- `scp`（WSL / Git Bash / PowerShell 均可）

### 宿主机硬件初始化（一次性操作 — 必须在 Thor 裸机上执行）

以下操作在启动 Docker 容器**之前**完成。配置一次后，容器通过 `--privileged --network host` 继承这些接口。

**CAN 总线：**

```bash
sudo ip link set can4 down || true
sudo ip link set can4 type can bitrate 500000
sudo ip link set can4 up
ip -details link show can4
candump can4           # 确认底盘有 CAN 帧输出
```

**LiDAR 网络：**

```bash
# 确保 Thor 网口 IP 为 192.168.1.50/24（与 mid360_livox_config.json 一致）
sudo ip addr add 192.168.1.50/24 dev eth0
```

> 如果 Thor 实际网口不是 `192.168.1.50/24`，需：1) 先改 Thor 网口 2) 再改仓库中的 `mid360_livox_config.json`。

## 3. 使用步骤

### 第 1 步：把代码传到 Thor

```bash
# 方式 A：在 Thor 上 git clone（推荐）
ssh <your_user>@<thor_ip>
git clone <your-repo-url> ~/workspaces/MK-mini_ws

# 方式 B：从 Windows SCP 传
scp -r E:\Codex_ws\MK-mini_ws <your_user>@<thor_ip>:~/workspaces/
```

### 第 2 步：在 Thor 上构建镜像

> ⚠️ **必须在 Thor 上构建。** Windows (x86_64) 构建的镜像在 Thor (ARM64) 上无法运行。

```bash
cd ~/workspaces/MK-mini_ws/docker
docker build -t mkmini-jazzy:dev .
```

### 第 3 步：启动容器

```bash
cd ~/workspaces/MK-mini_ws/docker
bash run_mkmini_dev.sh
```

每次需要进入容器开发/测试时执行即可。容器退出后自动删除（`--rm`），代码不受影响。

## 4. 场景手册

以下各场景均在内启动后执行。所有脚本和命令**无需手动记容器路径**。

### 约定：容器内路径映射

| 裸机文档中的路径 | 容器内等效路径 |
|---|---|
| `~/ROS2_MK-mini` | `/workspaces/MK-mini_ws/ROS2_MK-mini` |
| `~/neupan_mkmini_ws` | `/workspaces/MK-mini_ws/neupan_mkmini_ws` |
| `/tmp/mkmini_odom_test.csv` | `/tmp/mkmini_odom_test.csv` 或挂载路径 |

---

### 4.1 底盘 SDK 构建

对标文档：`quick_start.md`、`odom_accuracy_test_plan.md`、`bringup_checklist.md`、`thor_mkmini_control_plan.md`

```bash
bash docker/scripts/build_chassis_sdk.sh
```

等效于：
```bash
source /opt/ros/jazzy/setup.bash
cd /workspaces/MK-mini_ws/ROS2_MK-mini
rm -rf build install log      # 自动清理跨架构残留
colcon build --symlink-install --packages-select yhs_can_interfaces yhs_can_control
```

---

### 4.2 底盘快速启动（quick_start.md）

**检查 CAN 总线：**

```bash
bash docker/scripts/check_can.sh       # 状态检查
bash docker/scripts/check_can.sh 5     # 状态检查 + 抓取 5 秒 CAN 帧
```

**启动底盘驱动：**

```bash
source /opt/ros/jazzy/setup.bash
source /workspaces/MK-mini_ws/ROS2_MK-mini/install/setup.bash
ros2 launch yhs_can_control yhs_can_control.launch.py
```

**检查话题和 TF（另开一个容器终端）：**

```bash
source /opt/ros/jazzy/setup.bash
source /workspaces/MK-mini_ws/ROS2_MK-mini/install/setup.bash

ros2 topic list
ros2 topic echo /chassis_info_fb
ros2 topic echo /odom
ros2 topic hz /chassis_info_fb
ros2 run tf2_ros tf2_echo odom base_link
```

**发指令测试运动：**

```bash
bash docker/scripts/send_cmd_vel.sh forward       # 前进 0.05 m/s
bash docker/scripts/send_cmd_vel.sh forward 0.1    # 前进 0.1 m/s
bash docker/scripts/send_cmd_vel.sh turn           # 轻微转向
bash docker/scripts/send_cmd_vel.sh stop           # 停车
```

> ⚠️ 首次运动测试必须架空驱动轮或在受控测试区域进行。

---

### 4.3 里程计精度测试（odom_accuracy_test_plan.md）

**前提：** 底盘驱动已在另一个终端启动（见 4.2）。

**运行测试：**

```bash
# 1.0 m 低速测试
bash docker/scripts/run_odom_test.sh --distance 1.0 --speed 0.05

# 2.0 m 测试，输出到挂载目录
bash docker/scripts/run_odom_test.sh --distance 2.0 --speed 0.05 \
    --csv /workspaces/MK-mini_ws/odom_results.csv
```

**建议的完整测试矩阵：**

| 轮次 | 目标距离 | 速度 | 重复 | 命令 |
|---|---|---|---|---|
| 1 | 0.5 m | 0.05 m/s | 3 | `--distance 0.5 --speed 0.05` |
| 2 | 1.0 m | 0.05 m/s | 3 | `--distance 1.0 --speed 0.05` |
| 3 | 2.0 m | 0.05 m/s | 3 | `--distance 2.0 --speed 0.05` |
| 4 | 1.0 m | 0.1 m/s | 3 | `--distance 1.0 --speed 0.1` |
| 5 | 2.0 m | 0.1 m/s | 3 | `--distance 2.0 --speed 0.1` |

**误差计算：**

```text
距离误差 = 里程计距离 - 实测距离
误差率   = (里程计距离 - 实测距离) / 实测距离 × 100%
```

验收标准：1.0 m 和 2.0 m 直线测试的平均距离误差 < 5%，车头偏航 < 5°。

---

### 4.4 底盘启动检查清单（bringup_checklist.md）

在 Docker 容器内逐项验证：

```bash
# CAN 检查
bash docker/scripts/check_can.sh 3

# 构建
bash docker/scripts/build_chassis_sdk.sh

# 启动驱动
source /opt/ros/jazzy/setup.bash
source /workspaces/MK-mini_ws/ROS2_MK-mini/install/setup.bash
ros2 launch yhs_can_control yhs_can_control.launch.py

# 验证话题
ros2 topic list | grep -E 'ctrl_cmd|chassis_info_fb|odom|cmd_vel'
ros2 run tf2_ros tf2_echo odom base_link

# 架空轮测试
bash docker/scripts/run_odom_test.sh --distance 0.5 --speed 0.05
```

---

### 4.5 Thor 控制验证（thor_mkmini_control_plan.md）

参照 `thor_mkmini_control_plan.md` 中的步骤顺序，所有 `ros2` 命令在容器内执行，CAN 和网络在宿主机配置。

关键验证点：

```bash
# 启动驱动并验证 /odom
ros2 launch yhs_can_control yhs_can_control.launch.py
ros2 topic echo /odom

# Nav2 接口检查（如果已构建 NeuPAN 环境）
ros2 launch mkmini_neupan_bringup navigation.launch.py
ros2 topic echo /nav2/baseline_cmd_vel
```

---

### 4.6 NeuPAN 全栈（neupan_mkmini_ws）

对标文档：`neupan_mkmini_ws/README.md`、`acceptance-test.md`

**首次初始化（只需执行一次）：**

```bash
source /opt/ros/jazzy/setup.bash
cd /workspaces/MK-mini_ws/neupan_mkmini_ws

# 拉取外部源码
vcs import . < mkmini_neupan.repos

# 复制底盘包
cp -a /workspaces/MK-mini_ws/ROS2_MK-mini/src/yhs_can_control src/
cp -a /workspaces/MK-mini_ws/ROS2_MK-mini/src/yhs_can_interfaces src/

# 锁定外部仓库版本（可选）
bash scripts/freeze_revisions.sh
```

**构建全栈：**

```bash
bash docker/scripts/build_neupan_full.sh
```

**启动全栈：**

```bash
source /opt/ros/jazzy/setup.bash
source /workspaces/MK-mini_ws/neupan_mkmini_ws/install/setup.bash
ros2 launch mkmini_neunan_bringup full_stack.launch.py
```

**验收测试录制（参照 acceptance-test.md）：**

```bash
cd /workspaces/MK-mini_ws/neupan_mkmini_ws
source install/setup.bash
bash scripts/record_acceptance_run.sh <run_name>
```

---

### 4.7 运行单元测试

```bash
# 全部测试
bash docker/scripts/run_tests.sh

# 仅底盘 C++ 测试（colcon test）
bash docker/scripts/run_tests.sh --chassis-only

# 仅安全桥 Python 测试（pytest）
bash docker/scripts/run_tests.sh --bridge-only
```

单元测试无需连接任何硬件即可运行。

## 5. 宿主机 vs 容器责任矩阵

| 操作 | 在哪里执行 | 命令 |
|---|---|---|
| CAN 接口配置 | **宿主机** | `sudo ip link set can4 up type can bitrate 500000` |
| LiDAR 网络配置 | **宿主机** | `sudo ip addr add 192.168.1.50/24 dev eth0` |
| 构建 Docker 镜像 | **宿主机** | `cd docker && docker build -t mkmini-jazzy:dev .` |
| 启动容器 | **宿主机** | `bash docker/run_mkmini_dev.sh` |
| CAN 诊断 | 容器内 | `bash docker/scripts/check_can.sh 5` |
| SDK 构建 | 容器内 | `bash docker/scripts/build_chassis_sdk.sh` |
| ROS 2 启动 | 容器内 | `ros2 launch ...` |
| 手动运动指令 | 容器内 | `bash docker/scripts/send_cmd_vel.sh forward` |
| 里程计测试 | 容器内 | `bash docker/scripts/run_odom_test.sh --distance 1.0` |
| 单元测试 | 容器内 | `bash docker/scripts/run_tests.sh` |
| NeuPAN 初始化 | 容器内 | `vcs import ...`（参见 4.6） |
| NeuPAN 全栈构建 | 容器内 | `bash docker/scripts/build_neupan_full.sh` |
| rosbag 录制 | 容器内 | `bash scripts/record_acceptance_run.sh` |

## 6. 常见问题排查

| 现象 | 可能原因 | 解决方法 |
|---|---|---|
| `can4: No such device` | CAN 未在宿主机配置 | 在 Thor 宿主机上执行 `sudo ip link set can4 up type can bitrate 500000`，确认 `ip link show can4` 存在且 UP |
| `candump can4` 无数据 | 底盘未上电/急停/CAN 接线 | 检查底盘电源、急停状态、CAN 适配器连接，在宿主机上排查 |
| 无法连接 Livox LiDAR | 网口 IP 不是 `192.168.1.50/24` | 宿主机上：`sudo ip addr add 192.168.1.50/24 dev eth0` |
| `colcon build` 失败 | 跨架构残留或依赖缺失 | `rm -rf build install log` 后重试 |
| `rosdep: command not found` | rosdep 未初始化 | 容器内手动执行 `rosdep init && rosdep update` |
| DDS 节点互相不可见 | 防火墙或 ROS_DOMAIN_ID 不一致 | Thor 宿主机可能需要 `sudo ufw disable`。确认所有终端使用相同 ROS_DOMAIN_ID |
| 镜像构建失败（x86_64） | 在 Windows 上构建 | **必须在 Thor 上构建。** Docker 不支持跨架构运行 |
| 容器退出后 CSV 日志丢失 | 写在 `/tmp` 内 | 使用 bind mount 路径：`--csv /workspaces/MK-mini_ws/results.csv` |
| build 目录权限问题 | 容器内以 root 运行 | 在 Thor 宿主机上：`sudo chown -R $USER:$USER ~/workspaces/` |

## 7. 未来生产化注意事项

- **非 root 用户：** 可在 Dockerfile 中创建与 Thor 主机 UID/GID 一致的用户
- **GPU 加速：** 在 `run_mkmini_dev.sh` 中添加 `--runtime=nvidia`
- **权限最小化：** 生产部署时将 `--privileged` 替换为精确的 `--cap-add` 和 `--device` 参数
- **CI/CD：** 可增加 entrypoint 脚本自动执行 `vcs import` → `colcon build` → 测试 → 启动

## 8. 参考文件

| 文件 | 用途 |
|---|---|
| `docker/Dockerfile` | 镜像定义（仅环境） |
| `docker/run_mkmini_dev.sh` | 容器启动脚本 |
| `docker/README.md` | 本文档 |
| `docker/scripts/build_chassis_sdk.sh` | 底盘 SDK 构建 |
| `docker/scripts/build_neupan_full.sh` | NeuPAN 全栈构建 |
| `docker/scripts/check_can.sh` | CAN 总线诊断 |
| `docker/scripts/run_odom_test.sh` | 里程计精度测试 |
| `docker/scripts/send_cmd_vel.sh` | 安全运动指令 |
| `docker/scripts/run_tests.sh` | 单元测试合集 |
| `neupan_mkmini_ws/scripts/bootstrap_jazzy.sh` | 完整环境引导脚本（依赖参考） |
| `neupan_mkmini_ws/mkmini_neupan.repos` | 外部源码仓库清单 |
