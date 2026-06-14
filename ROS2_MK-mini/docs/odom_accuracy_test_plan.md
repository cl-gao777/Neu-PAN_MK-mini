# MK-mini 里程计精度测试计划

本文档用于在 Thor 上位机 Ubuntu 24.04 + ROS 2 Jazzy 环境中，验证 MK-mini 当前 SDK 发布的 `/odom` 是否准确。测试方法是：上位机按目标距离发送低速 `/cmd_vel`，节点根据 `/odom` 自动停车，再用卷尺、地面标线或外部定位系统测量真实距离并计算误差。

## 目标

- 验证 `/odom` 的直线距离累计是否可信。
- 对比 `/odom` 位移、底盘累计里程反馈和外部实测距离。
- 在接入 Nav2 前发现比例误差、方向错误、累计里程跳变或 TF 更新问题。

注意：测试节点使用 `/odom` 判断何时停车，所以“车辆在 `/odom` 到达 1 m 时停下”不等于里程计准确。最终结论必须以外部实测距离为准。

## 前提条件

- Thor 使用 Ubuntu 24.04 + ROS 2 Jazzy。
- 项目位于 Thor 原生 Linux 路径，例如 `~/ROS2_MK-mini`。
- 不建议使用 `/mnt/e/...` 这类 Windows 挂载路径作为正式运行工作区。
- 当前 Thor + PEAK PCAN-USB 部署默认 CAN 接口名为 `can4`，波特率为 `500000`；如果实际接口名不同，请按 `ip link` 结果覆盖 `can_name`。
- 首次测试必须架空车轮或在安全测试区域进行。
- 默认不测试倒车，保持 `allow_reverse=false`。

## 构建 SDK

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

构建通过后，确认测试工具已安装：

```bash
ros2 run yhs_can_control odom_distance_test_node --ros-args -p armed:=false
```

`armed=false` 是默认值，此时节点不会发布非零运动指令。

## CAN 检查

先确认接口名：

```bash
ip link
```

配置 `can4`：

```bash
sudo ip link set can4 down || true
sudo ip link set can4 type can bitrate 500000
sudo ip link set can4 up
ip -details link show can4
```

检查底盘反馈：

```bash
candump can4
```

如果 `candump can4` 没有数据，先排查 CANH/CANL、波特率、急停、电源和 CAN 适配器驱动，不要急着启动 ROS 节点。

## 启动驱动

终端 1：

```bash
cd ~/ROS2_MK-mini
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch yhs_can_control yhs_can_control.launch.py
```

终端 2 检查话题和 TF：

```bash
source /opt/ros/jazzy/setup.bash
source ~/ROS2_MK-mini/install/setup.bash
ros2 topic list
ros2 topic echo /chassis_info_fb
ros2 topic echo /veh_diag_fb
ros2 topic echo /odom
ros2 run tf2_ros tf2_echo odom base_link
```

最低要求：

- `/chassis_info_fb` 有连续聚合反馈数据。
- `/veh_diag_fb` 有连续诊断反馈数据。
- `/odom` 在车轮运动时连续更新。
- `odom -> base_link` TF 能查询到。

## 架空轮预检查

先架空车轮，运行 0.5 m 的低速测试：

```bash
ros2 run yhs_can_control odom_distance_test_node --ros-args \
  -p armed:=true \
  -p target_distance_m:=0.5 \
  -p target_speed_mps:=0.3
```

预期现象：

- 车轮低速前进。
- `/odom` 增加到目标距离附近后，测试节点发布 0 速。
- 结束后节点继续保持 0 速至少 `stop_hold_sec`，默认 1 秒。
- 终端输出结束原因、目标距离、里程计距离、底盘累计里程变化和运行时间。

如果车轮方向与 `/odom` 方向不一致，先停止测试并排查底盘反馈解析、坐标系方向和 CAN 协议版本。

## 地面直线测试

在平整地面贴起点线和终点参考线。建议从短距离开始：

| 轮次 | 目标距离 | 目标速度 | 重复次数 |
| --- | --- | --- | --- |
| 1 | `0.5 m` | `0.3 m/s` | 3 |
| 2 | `1.0 m` | `0.3 m/s` | 3 |
| 3 | `2.0 m` | `0.3 m/s` | 3 |
| 4 | `1.0 m` | `0.5 m/s` | 3 |
| 5 | `2.0 m` | `0.5 m/s` | 3 |

示例命令：

```bash
ros2 run yhs_can_control odom_distance_test_node --ros-args \
  -p armed:=true \
  -p target_distance_m:=1.0 \
  -p target_speed_mps:=0.3 \
  -p log_csv_path:=/tmp/mkmini_odom_test.csv
```

CSV 日志字段：

- `timestamp`
- `target_distance_m`
- `target_speed_mps`
- `odom_start_x`
- `odom_start_y`
- `odom_end_x`
- `odom_end_y`
- `odom_distance_m`
- `chassis_mileage_delta_m`
- `runtime_sec`
- `end_reason`

## 误差计算

每次测试都记录：

- 目标距离。
- `/odom` 输出的位移。
- `/chassis_info_fb.odo_fb.odo_fb_accumulative_mileage` 的增量。
- 外部实测距离。
- 车头最终偏航或横向偏移。

误差公式：

```text
距离误差 = 里程计距离 - 实测距离
误差率 = (里程计距离 - 实测距离) / 实测距离 * 100%
```

记录模板：

| 日期 | 目标距离 | 目标速度 | `/odom` 距离 | 底盘累计里程增量 | 实测距离 | 误差率 | 横向偏移 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | `1.0 m` | `0.3 m/s` | | | | | | |

## 初始验收标准

- `colcon build --symlink-install` 通过。
- `candump can4` 能看到底盘反馈。
- `ros2 launch yhs_can_control yhs_can_control.launch.py` 能启动。
- `/chassis_info_fb`、`/veh_diag_fb`、`/odom` 和 `odom -> base_link` TF 正常更新。
- `odom_distance_test_node` 能在到达目标距离、超时或异常时自动停车。
- 直线 `1.0 m` 和 `2.0 m` 的平均距离误差建议先控制在 5% 以内。
- `2.0 m` 直线测试的车头偏航建议先控制在 5 度以内。

如果误差超过上述建议值，不要直接接入 Nav2，应先排查轮径、轮速反馈、底盘累计里程反馈、坐标系方向、地面打滑和 CAN 协议解析。

## 常见问题

| 现象 | 优先检查 | 处理建议 |
| --- | --- | --- |
| 节点只提示 `armed=false` | 启动参数 | 显式添加 `-p armed:=true`。 |
| 节点等待 `/odom` | `/odom`、`/chassis_info_fb` | 先确认驱动节点启动且底盘有反馈。 |
| 到达目标距离前超时 | `target_speed_mps`、`max_runtime_sec` | 先确认车轮是否实际运动，再适当增加 `max_runtime_sec`。 |
| CSV 没有生成 | `log_csv_path` | 使用 Thor 上可写路径，例如 `/tmp/mkmini_odom_test.csv`。 |
| 实测距离和 `/odom` 差异大 | 地面、轮径、反馈解析 | 重复测试并检查是否打滑或协议缩放错误。 |
| 停车后仍继续运动 | `/cmd_vel`、急停、底盘状态 | 立即急停，检查是否有其他节点同时发布 `/cmd_vel` 或 `/ctrl_cmd`。 |
