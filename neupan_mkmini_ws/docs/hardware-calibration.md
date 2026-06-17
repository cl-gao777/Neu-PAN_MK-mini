# 硬件标定

## 必需测量

记录 Mid-360 相对于 `base_link` 的位姿：

- 平移：`x`、`y`、`z`，单位为米。
- 旋转：roll、pitch、yaw，单位为弧度。

完成实测并在 RViz 中验证该变换前，禁止进行 SLAM 或障碍净空测试。

`mid360_livox_config.json` 中的零 `extrinsic_parameter` 只作为 Livox driver 占位值，
不代表机器人已经完成实测外参。真机运行时，LiDAR/IMU 外参和
`base_link -> livox_frame` 应写入 FAST-LIO 配置或由 TF 发布。除非物理测量证明零外参成立，
否则不得把零外参用于闭环导航。

## TF 发布权

完整集成栈优先使用 FAST-LIO2 作为 `odom -> base_link` 发布者。FAST-LIO2 稳定后，
将 `yhs_can_control_node` 的 `publish_odom_tf` 设置为 `false`。底盘里程计话题仍应保留，
用于对比分析。

## 点云切片

启动 `pointcloud_to_laserscan` 前，应保持 `livox_ros_driver2` 发布
`livox_ros_driver2/msg/CustomMsg` 给 FAST-LIO2 使用，并使用
`custom_msg_to_pointcloud2` 将 `/livox/lidar` 转换为 `/livox/points`
(`sensor_msgs/PointCloud2`) 给 `pointcloud_to_laserscan` 使用。

建议从以下参数开始：

- `min_height: -0.20`
- `max_height: 1.20`
- `range_min: 0.30`
- `range_max: 20.0`

在点云上叠加显示 `/scan`。逐步调整高度范围，在保留腿部、箱体和低矮障碍物的同时，
排除地面回波和高处物体。

调参时应确认 `/livox/points` 只有一个有效发布者。若 `full_stack.launch.py`
以 `start_scan_pipeline:=true` 启动，则它会自动启动 `/livox/lidar -> /livox/points`
转换旁路，不应再让 `fast_lio_mid360.launch.py start_visualization_cloud:=true` 同时发布。

## DUNE 几何准入条件

提供的 NeuPAN 配置使用 `0.84 m x 0.60 m` 矩形车体和 `0.60 m` 轴距。
真机 NeuPAN 测试前，必须训练并验证匹配该几何外形的 DUNE checkpoint。
禁止使用 Ranger 或差速车 checkpoint 代替真机模型。
