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

为 MK-mini 配置 `neupan_ros2`：

- kinematics：`acker`
- wheelbase：`0.6`
- 最大速度：`0.3 m/s`
- 最大转向角：`0.436332 rad`（`25 deg`）
- 输入激光话题：`/scan`
- 输入路径话题：`/plan`
- TF：`map -> base_link`
- 输出话题：`/neupan_cmd_vel`

使用 `config/neupan_mkmini.yaml` 作为几何和训练基线。启动 NeuPAN 前，必须替换
`REPLACE_WITH_TRAINED_MKMINI_DUNE_CHECKPOINT`。

## 推荐的上游改进

对上游 wrapper 建立 fork 后，可在阿克曼模式下直接向 `/neupan/ackermann_cmd`
发布 `AckermannDriveStamped`。随后使用以下命令启动控制栈：

```bash
ros2 launch mkmini_neupan_bridge mkmini_neupan_control.launch.py \
  use_legacy_adapter:=false
```

直接 Ackermann 输出通过相同的架空轮和超时停车测试前，应继续保留兼容适配器。
无论采用哪种输出方式，都不得移除安全桥。
