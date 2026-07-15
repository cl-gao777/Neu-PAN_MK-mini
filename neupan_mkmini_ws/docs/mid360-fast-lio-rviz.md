# MID-360、FAST-LIO 与 RViz 点云监测

本页说明如何把 MID-360 接入 FAST-LIO，同时在 RViz 中实时查看点云。核心原则是算法链路和可视化链路分开：

```text
/livox/lidar  livox_ros_driver2/msg/CustomMsg  -> FAST-LIO
/livox/imu    Livox IMU 数据                   -> FAST-LIO
/livox/lidar  livox_ros_driver2/msg/CustomMsg  -> /livox/points PointCloud2 -> RViz
```

`/livox/points` 只是可视化和二维扫描转换旁路，不是 FAST-LIO 的主输入。仅启动 RViz 点云监测时，不会自动启动 `/scan`、SLAM Toolbox、Nav2 或 NeuPAN。

## Thor 网络配置

MID-360 连接到 Thor 的 `enP2p1s0` 网口时，先配置主机 IP：

```bash
sudo ip addr add 192.168.1.50/24 dev enP2p1s0
ping 192.168.1.3
```

仓库默认 MID-360 配置使用以下约定：

- Thor 网口：`enP2p1s0`
- Thor IP：`192.168.1.50`
- MID-360 IP：`192.168.1.3`
- LiDAR CustomMsg 话题：`/livox/lidar`
- IMU 话题：`/livox/imu`
- 发布频率：约 `10 Hz`

## 仅运行 FAST-LIO 与 RViz 点云旁路

在 Thor ROS2 Jazzy 环境中：

```bash
cd ~/workspaces/MK-mini_ws/neupan_mkmini_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash

ros2 launch mkmini_neupan_bringup fast_lio_mid360.launch.py \
  start_mid360:=true \
  start_fast_lio:=true \
  start_visualization_cloud:=true \
  start_rviz:=false
```

如果已经配置 GUI、X11 或 Wayland 转发，可以同一个 launch 中打开 RViz：

```bash
ros2 launch mkmini_neupan_bringup fast_lio_mid360.launch.py \
  start_mid360:=true \
  start_fast_lio:=true \
  start_visualization_cloud:=true \
  start_rviz:=true
```

也可以单独开 RViz：

```bash
ros2 launch mkmini_neupan_bringup mid360_rviz.launch.py
```

`mid360_rviz.launch.py` 会先把 RViz 模板复制到 `/tmp/mkmini_mid360_fast_lio.rviz` 再启动 RViz，避免 `colcon build --symlink-install` 场景下 RViz 保存窗口状态时污染源码模板。

## 接入 full_stack 与 NeuPAN

如果后续要让 NeuPAN 使用 MID-360 障碍物输入，仍然不要把 FAST-LIO 的主输入改成 PointCloud2。正确链路是：

```text
/livox/lidar CustomMsg -> FAST-LIO
/livox/lidar CustomMsg -> /livox/points PointCloud2 -> /scan LaserScan -> SLAM Toolbox / Nav2 / NeuPAN
```

推荐做法是让 FAST-LIO 终端只负责 MID-360 driver 和 FAST-LIO，不发布 `/livox/points`：

```bash
ros2 launch mkmini_neupan_bringup fast_lio_mid360.launch.py \
  start_mid360:=true \
  start_fast_lio:=true \
  start_visualization_cloud:=false \
  start_rviz:=false
```

然后由 `full_stack.launch.py start_scan_pipeline:=true` 负责 `/livox/lidar -> /livox/points -> /scan`：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py \
  start_mid360:=false \
  start_visualization_cloud:=false \
  start_scan_pipeline:=true \
  start_neupan:=false
```

当 DUNE checkpoint、`/scan`、`/plan`、TF 和安全桥都通过检查后，再打开 NeuPAN：

```bash
ros2 launch mkmini_neupan_bringup full_stack.launch.py \
  start_mid360:=false \
  start_visualization_cloud:=false \
  start_scan_pipeline:=true \
  start_neupan:=true
```

不要同时让 `fast_lio_mid360.launch.py start_visualization_cloud:=true` 和 `full_stack.launch.py start_scan_pipeline:=true` 发布 `/livox/points`，否则 RViz 和 `/scan` 可能看到重复发布者。

## 验证命令

先确认 MID-360 和 FAST-LIO 输入：

```bash
ros2 topic hz /livox/lidar
ros2 topic info /livox/lidar -v
ros2 topic hz /livox/imu
```

再确认 RViz 旁路：

```bash
ros2 topic hz /livox/points
ros2 topic info /livox/points -v
ros2 topic echo /livox/points --once
```

接入 full stack 后继续检查：

```bash
ros2 topic hz /scan
ros2 topic hz /plan
ros2 run tf2_ros tf2_echo odom base_link --once
ros2 run tf2_ros tf2_echo map base_link --once
```

RViz 中的 `PointCloud2` display 应显示 `/livox/points`，默认 Fixed Frame 为 `livox_frame`。如果已经发布 `base_link -> livox_frame` 或定位 TF，可按调试需要切换到 `base_link`、`odom` 或 `map`。

## 外参语义

`mid360_livox_config.json` 中的零 `extrinsic_parameter` 只作为 Livox driver 占位值，不代表已经完成机器人实测外参。

真机运行时，LiDAR/IMU 外参和 `base_link -> livox_frame` 应来自实测，并写入 FAST-LIO 配置或 TF。除非物理测量证明零外参确实成立，否则禁止把零外参当作可用于闭环导航的安全配置。
