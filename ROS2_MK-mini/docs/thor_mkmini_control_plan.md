# Thor 控制 MK-mini 验证计划

本文档用于验证 Thor 上位机能否在 Ubuntu 24.04 + ROS 2 Jazzy 环境中运行
`ROS2_MK-mini` SDK，并通过 CAN 控制 MK-mini 底盘。验证顺序是：先确认构建，
再确认 CAN 通讯，再启动 ROS 2 节点，最后做架空车轮低速测试。

## 1. 目标

最低目标不是直接接入 Nav2 自动导航，而是确认 Thor 能稳定跑起当前底盘中间件：

- Thor 能在 ROS 2 Jazzy 下完成 `colcon build --symlink-install`。
- Thor 能通过当前默认接口 `can4` 收到底盘 CAN 反馈。
- `yhs_can_control_node` 和 `cmd_vel_to_ctrl_cmd_node` 能正常启动。
- `/chassis_info_fb`、`/veh_diag_fb`、`/odom` 和 `odom -> base_link` TF 能更新。
- 架空车轮状态下，低速 `/cmd_vel` 能触发底盘响应。
- 停止发布 `/cmd_vel` 后，约 `0.3s` 自动回到 0 速。

## 2. 前提条件

- Thor 系统为 Ubuntu 24.04。
- Thor 已安装 ROS 2 Jazzy。
- MK-mini 底盘已上电，急停状态允许测试。
- CAN 适配器已连接 Thor。
- CANH 和 CANL 接线正确。
- 首次运动测试时，车轮必须架空，或车辆处于受控测试区域。

默认安全参数来自 `src/yhs_can_control/params/cfg.yaml`：

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `max_velocity_mps` | `0.6` | 底盘 SDK `/cmd_vel` 适配器速度硬限幅，单位 m/s。 |
| `max_steering_deg` | `25.0` | 最大转向角，单位度。 |
| `allow_reverse` | `false` | 默认禁止倒车。 |
| `cmd_vel_timeout_sec` | `0.3` | 超时停车时间，单位秒。 |
| `use_stamped_cmd_vel` | `false` | 默认使用 `geometry_msgs/msg/Twist`。 |

## 3. 文件迁移到 Thor

在 Thor 上使用原生 Linux 工作区，例如：

```bash
mkdir -p ~/ROS2_MK-mini
```

将项目内容复制到 Thor 后，推荐结构为：

```text
~/ROS2_MK-mini/
  src/
    yhs_can_control/
    yhs_can_interfaces/
  docs/
  README.md
```

不要在 Thor 上使用 `/mnt/e/...` 这类 Windows 挂载路径作为正式运行工作区。
复制到 Thor 时不要带 `build/`、`install/`、`log/`。如果已经复制过去，可在
Thor 上删除：

```bash
cd ~/ROS2_MK-mini
rm -rf build install log
```

## 4. Thor 端构建验证

在 Thor 上执行：

```bash
cd ~/ROS2_MK-mini
source /opt/ros/jazzy/setup.bash
sudo apt update
sudo apt install -y python3-colcon-common-extensions python3-rosdep can-utils
rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

构建通过表示当前 SDK 能在 Thor/Jazzy 上完成基本编译和安装。若构建失败，先保存
完整终端日志，再检查：

- 是否正确 `source /opt/ros/jazzy/setup.bash`。
- 是否在 `~/ROS2_MK-mini` 工作区根目录执行。
- `src/yhs_can_control` 和 `src/yhs_can_interfaces` 是否存在。
- `rosdep install` 是否成功安装依赖。

## 5. CAN 通讯验证

先确认 CAN 接口名：

```bash
ip link
```

当前 Thor + PEAK PCAN-USB 部署默认接口名是 `can4`。如果 `ip link` 显示的
实际接口名不同，请把下面命令中的 `can4` 替换为实际接口名，并同步覆盖
`can_name` 参数。

```bash
sudo ip link set can4 down || true
sudo ip link set can4 type can bitrate 500000
sudo ip link set can4 up
ip -details link show can4
```

检查底盘是否有 CAN 反馈：

```bash
candump can4
```

如果 `candump can4` 没有任何数据，不要急着启动 ROS 节点。优先排查：

- CANH/CANL 是否接反。
- 波特率是否为 `500000`。
- MK-mini 是否上电。
- 急停是否释放。
- CAN 适配器驱动是否正常。
- 接口名是否不是 `can4`，以及 `can_name` 是否同步覆盖。

只有 `candump can4` 能看到底盘反馈后，再继续启动 ROS 2 驱动。

## 6. 启动 MK-mini 驱动

终端 1 启动驱动：

```bash
cd ~/ROS2_MK-mini
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch yhs_can_control yhs_can_control.launch.py
```

该 launch 会启动：

- `yhs_can_control_node`：SocketCAN 扩展帧桥接、底盘反馈解析、`/chassis_info_fb`、
  `/veh_diag_fb`、`/odom` 和 TF。
- `cmd_vel_to_ctrl_cmd_node`：将 `/cmd_vel` 转成 `/ctrl_cmd`。

若启动时报 `can4` 或实际 `can_name` 相关错误，回到 CAN 通讯验证步骤。

## 7. 话题与 TF 检查

终端 2 执行：

```bash
source /opt/ros/jazzy/setup.bash
source ~/ROS2_MK-mini/install/setup.bash
ros2 topic list
```

应能看到以下关键话题：

- `/ctrl_cmd`
- `/io_cmd`
- `/cmd_vel`
- `/chassis_info_fb`
- `/veh_diag_fb`
- `/odom`
- `/tf`

检查底盘反馈：

```bash
ros2 topic echo /chassis_info_fb
ros2 topic echo /veh_diag_fb
```

检查里程计：

```bash
ros2 topic echo /odom
```

检查 TF：

```bash
ros2 run tf2_ros tf2_echo odom base_link
```

预期结果：

- `/chassis_info_fb` 能持续输出聚合底盘反馈。
- `/veh_diag_fb` 只在真实整车诊断 CAN 帧到达时更新。
- `/odom` 在有底盘里程计或速度反馈时更新。
- `odom -> base_link` TF 能查询到。

## 8. 架空车轮低速测试

开始运动测试前，先架空车轮，确认急停可用。

前进测试：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
"{linear: {x: 0.5}, angular: {z: 0.0}}"
```

转向测试：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
"{linear: {x: 0.5}, angular: {z: 0.1}}"
```

停止测试：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
"{linear: {x: 0.0}, angular: {z: 0.0}}"
```

也要验证超时停车：停止发布 `/cmd_vel` 后，约 `0.3s` 内应自动回到零速度指令。

## 9. 最低验收标准

满足以下条件后，才能认为“Thor 已经能跑起当前 MK-mini SDK”：

- [ ] `colcon build --symlink-install` 通过。
- [ ] `candump can4` 能看到底盘反馈。
- [ ] `ros2 launch yhs_can_control yhs_can_control.launch.py` 能启动。
- [ ] `/chassis_info_fb` 有连续数据。
- [ ] `/veh_diag_fb` 有连续诊断数据。
- [ ] `/odom` 能更新。
- [ ] `ros2 run tf2_ros tf2_echo odom base_link` 能查到 TF。
- [ ] 架空车轮状态下，`/cmd_vel` 低速前进指令能触发底盘响应。
- [ ] 架空车轮状态下，`/cmd_vel` 低速转向指令能触发转向反馈。
- [ ] 停止发布 `/cmd_vel` 后，超时停车有效。

完成上述验证后，再进入 Nav2 建图、定位或导航接入阶段。

## 10. 常见问题

| 现象 | 优先检查 | 处理方向 |
| --- | --- | --- |
| `colcon build` 失败 | ROS 环境、依赖、工作区结构 | 确认 Jazzy 已 source，执行 `rosdep install`。 |
| 没有 `can4` | `ip link` | 检查 CAN 适配器驱动和接口名称；接口名不同时覆盖 `can_name`。 |
| `candump can4` 没有帧 | CANH/CANL、波特率、电源、急停 | 先修复 CAN 通讯，不要启动 ROS 节点。 |
| launch 打不开 CAN | `ip -details link show can4` | 确认 `can4` 已 `UP`，或修改 `can_name` 参数。 |
| `/chassis_info_fb` 不更新 | `candump can4` | 确认原始 CAN 帧存在，且协议版本匹配。 |
| `/veh_diag_fb` 不更新 | `candump can4`、诊断 CAN ID | 确认整车诊断扩展帧存在；安全桥诊断超时依赖该话题。 |
| `/odom` 不更新 | `/chassis_info_fb.ctrl_fb`、`/chassis_info_fb.odo_fb` | 确认底盘速度或里程计反馈存在。 |
| TF 查不到 | `publish_odom_tf`、`/odom` | 确认 `publish_odom_tf=true`，且 `/odom` 正常更新。 |
| 倒车无响应 | `allow_reverse` | 默认禁止倒车，只有安全验证后才可启用。 |
