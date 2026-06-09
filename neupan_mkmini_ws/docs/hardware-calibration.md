# 硬件标定

## 必需测量

记录 Mid-360 相对于 `base_link` 的位姿：

- 平移：`x`、`y`、`z`，单位为米。
- 旋转：roll、pitch、yaw，单位为弧度。

完成实测并在 RViz 中验证该变换前，禁止进行 SLAM 或障碍净空测试。

## TF 发布权

完整集成栈优先使用 FAST-LIO2 作为 `odom -> base_link` 发布者。FAST-LIO2 稳定后，
将 `yhs_can_control_node` 的 `publish_odom_tf` 设置为 `false`。底盘里程计话题仍应保留，
用于对比分析。

## 点云切片

启动 `pointcloud_to_laserscan` 前，应将 `livox_ros_driver2` 配置为发布
`sensor_msgs/PointCloud2`，而不是只发布 Livox 自定义消息。

建议从以下参数开始：

- `min_height: -0.20`
- `max_height: 1.20`
- `range_min: 0.30`
- `range_max: 20.0`

在点云上叠加显示 `/scan`。逐步调整高度范围，在保留腿部、箱体和低矮障碍物的同时，
排除地面回波和高处物体。

## DUNE 几何准入条件

提供的 NeuPAN 配置使用 `0.84 m x 0.60 m` 矩形车体和 `0.60 m` 轴距。
真机 NeuPAN 测试前，必须训练并验证匹配该几何外形的 DUNE checkpoint。
禁止使用 Ranger 或差速车 checkpoint 代替真机模型。
