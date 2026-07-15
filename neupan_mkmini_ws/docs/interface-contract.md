# 接口约定

## 坐标系

- `map -> odom`：在线建图期间由 SLAM Toolbox 发布。
- `odom -> camera_init`：集成层发布单位静态变换。
- `camera_init -> body`：FAST_LIO 固定发布的动态变换。
- `body -> base_link`：实测 `base_link -> livox_frame` 的逆变换。
- `base_link -> livox_frame`：必须使用实测静态变换，禁止使用未经测量的零变换。

这里假设 FAST_LIO 的 `body` 与 MID360 IMU/livox 物理坐标系重合。完整链为
`odom -> camera_init -> body -> base_link -> livox_frame`。配置默认
`calibrated: false`，启用 TF 集成时会 fail-safe 退出；底盘 `publish_odom_tf` 必须关闭。

正式安全桥持续检查 `map -> base_link`。变换不可用、超过
`localization_timeout_sec` 或时间戳异常时，安全桥发布零速度。

## 话题

| 话题 | 类型 | 发布者 | 使用者 |
| --- | --- | --- | --- |
| `/livox/lidar` | `livox_ros_driver2/msg/CustomMsg` | Livox 驱动 | FAST-LIO2、custom-msg-to-pointcloud2 |
| `/livox/points` | `sensor_msgs/PointCloud2` | custom-msg-to-pointcloud2 | pointcloud-to-laserscan、RViz |
| `/Odometry` | `nav_msgs/Odometry` | FAST_LIO | Nav2、preflight |
| `/odom` | `nav_msgs/Odometry` | YHS CAN 驱动 | 仅诊断 |
| `/scan` | `sensor_msgs/LaserScan` | pointcloud-to-laserscan | SLAM Toolbox、Nav2、NeuPAN |
| `/plan` | `nav_msgs/Path` | Nav2 planner | NeuPAN |
| `/neupan_cmd_vel` | `geometry_msgs/Twist` | 上游 NeuPAN ROS2 | 仅兼容适配器 |
| `/neupan/ackermann_cmd` | `ackermann_msgs/AckermannDriveStamped` | 适配器或修改后的 NeuPAN | 安全桥 |
| `/veh_diag_fb` | `yhs_can_interfaces/VehDiagFb` | YHS CAN 驱动 | 安全桥 |
| `/ctrl_cmd` | `yhs_can_interfaces/CtrlCmd` | 安全桥 | YHS CAN 驱动 |

上游 ROS2 wrapper 使用 `Twist.angular.z` 表示阿克曼转向角（弧度），而不是偏航角速度。
兼容适配器会立即将其转换为 `AckermannDriveStamped`；其他节点不得将该话题当作普通
`cmd_vel` 使用。

`/livox/points` 只用于 RViz 显示和 `/scan` 转换旁路。FAST-LIO2 仍订阅
`/livox/lidar` 的 `livox_ros_driver2/msg/CustomMsg`，不得为了显示点云而把 FAST-LIO2
主输入改成 PointCloud2。`full_stack.launch.py start_scan_pipeline:=true` 会自动启动
`custom_msg_to_pointcloud2`，因此同一时间只能保留一个有效的 `/livox/points` 发布者。

安全桥使用 `/veh_diag_fb` 判断整车诊断帧是否健康且新鲜。`/chassis_info_fb` 仍是聚合底盘反馈，
但任意反馈帧都会刷新该聚合消息，不能作为诊断帧新鲜度来源。

## 控制单位

- NeuPAN 与 `AckermannDriveStamped`：速度单位为 m/s，转向角单位为弧度。
- MK-mini `/ctrl_cmd`：速度为非负的 m/s 数值，转向角单位为度。
- 档位定义：`P=1`、`R=2`、`N=3`、`D=4`。
