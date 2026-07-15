# 话题与参数

本文档说明 MK-mini SDK 对外公开的 ROS 2 接口，并与当前 Jazzy 适配实现保持一致。

## 节点

| 节点 | 可执行文件 | 职责 |
| --- | --- | --- |
| `yhs_can_control_node` | `yhs_can_control_node` | SocketCAN 扩展帧桥接、CAN 反馈解析、`/chassis_info_fb`、`/veh_diag_fb`、`/odom`、odom TF。 |
| `cmd_vel_to_ctrl_cmd_node` | `cmd_vel_to_ctrl_cmd_node` | 将 Nav2 风格的 `/cmd_vel` 指令转换为 MK-mini `/ctrl_cmd`。 |

默认 launch 文件会同时启动两个节点：

```bash
ros2 launch yhs_can_control yhs_can_control.launch.py
```

## 话题

| 话题 | 类型 | 方向 | 节点 | 说明 |
| --- | --- | --- | --- | --- |
| `/ctrl_cmd` | `yhs_can_interfaces/msg/CtrlCmd` | 订阅 | `yhs_can_control_node` | 底层底盘控制指令，也由 cmd_vel 适配器发布。 |
| `/io_cmd` | `yhs_can_interfaces/msg/IoCmd` | 订阅 | `yhs_can_control_node` | 灯光、喇叭、放电和 IO 控制指令。 |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | 订阅 | `cmd_vel_to_ctrl_cmd_node` | 默认 Nav2 速度指令输入。 |
| `/cmd_vel` | `geometry_msgs/msg/TwistStamped` | 可选订阅 | `cmd_vel_to_ctrl_cmd_node` | 当 `use_stamped_cmd_vel=true` 时启用。 |
| `/chassis_info_fb` | `yhs_can_interfaces/msg/ChassisInfoFb` | 发布 | `yhs_can_control_node` | 聚合后的底盘反馈，每解析到任意反馈帧都会更新。 |
| `/veh_diag_fb` | `yhs_can_interfaces/msg/VehDiagFb` | 发布 | `yhs_can_control_node` | 专用整车诊断反馈，仅在真实诊断 CAN 帧到达时更新。 |
| `/odom` | `nav_msgs/msg/Odometry` | 发布 | `yhs_can_control_node` | 优先使用底盘里程计反馈；不可用时使用速度积分回退。 |
| `/tf` | `tf2_msgs/msg/TFMessage` | 发布 | `yhs_can_control_node` | 当 `publish_odom_tf=true` 时发布 `odom -> base_link`。 |

## CtrlCmd

`/ctrl_cmd` 使用 `yhs_can_interfaces/msg/CtrlCmd`：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `ctrl_cmd_gear` | `uint8` | 底盘挡位指令。当前适配器默认前进为 `4`，倒车为 `2`。 |
| `ctrl_cmd_velocity` | `float32` | 目标速度，单位 m/s。CAN 协议编码时按 1000 倍缩放。 |
| `ctrl_cmd_steering` | `float32` | 目标转角，单位度。CAN 协议编码时按 100 倍缩放。 |

直接使用 `/ctrl_cmd` 的节点应发布非负速度。倒车测试建议使用 `/cmd_vel` 并设置
`allow_reverse=true`，这样适配器仍能应用配置好的安全限幅。

## IoCmd

`/io_cmd` 使用 `yhs_can_interfaces/msg/IoCmd`：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `io_cmd_enable` | `bool` | 启用 IO 指令处理。 |
| `io_cmd_lower_beam_headlamp` | `bool` | 近光灯。 |
| `io_cmd_upper_beam_headlamp` | `bool` | 远光灯。 |
| `io_cmd_turn_lamp` | `uint8` | 转向灯状态。 |
| `io_cmd_braking_lamp` | `bool` | 刹车灯。 |
| `io_cmd_clearance_lamp` | `bool` | 示廓灯。 |
| `io_cmd_fog_lamp` | `bool` | 雾灯。 |
| `io_cmd_speaker` | `bool` | 喇叭。 |
| `io_cmd_dis_charge` | `bool` | 放电控制。 |

## ChassisInfoFb

`/chassis_info_fb` 使用 `yhs_can_interfaces/msg/ChassisInfoFb`，聚合以下反馈：

| 字段 | 含义 |
| --- | --- |
| `header` | ROS 时间戳和坐标系元数据。 |
| `ctrl_fb` | 挡位、速度、转角和控制模式反馈。 |
| `io_fb` | IO 状态反馈。 |
| `lr_wheel_fb`, `rr_wheel_fb` | 后轮速度和脉冲反馈。 |
| `odo_fb` | 累计里程和累计角度反馈。 |
| `bms_flag_info_fb`, `bms_info_fb` | BMS 标志位、电压、电流、容量和温度。 |
| `drive_mcu_ecode_fb` | 驱动 MCU 错误码反馈。 |
| `veh_diag_fb` | 最近一次聚合到 `ChassisInfoFb` 的底盘诊断标志位。安全桥诊断新鲜度应使用专用 `/veh_diag_fb`。 |
| `ultrasonic` | 超声波距离反馈。 |

## 参数

默认参数位于 `src/yhs_can_control/params/cfg.yaml`。

### yhs_can_control_node

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `can_name` | `can4` | SocketCAN 接口名称；当前 Thor + PEAK PCAN-USB 使用 `can4`，可按实际接口覆盖。 |
| `wheel_base` | `0.6` | 轴距，单位米，用于里程计回退积分。 |
| `use_odo_angular` | `false` | 是否直接使用厂家 ODO 累计角度。当前 MK-mini 实测该字段恒为 0，默认用累计里程和实际转角按 Ackermann 模型积分航向。 |
| `publish_odom_tf` | `true` | 是否发布 `odom -> base_link` TF。 |
| `odom_frame_id` | `odom` | 里程计父坐标系。 |
| `base_frame_id` | `base_link` | 机器人底盘子坐标系。 |
| `ultrasonic_number` | `[0,1,2,3,4,5,6,7]` | 将接收到的超声波索引映射到反馈顺序。必须包含 8 个 0-7 范围内的索引。 |

### cmd_vel_to_ctrl_cmd_node

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `input_topic` | `cmd_vel` | 速度指令输入话题，相对名称。 |
| `output_topic` | `ctrl_cmd` | 底层控制指令输出话题，相对名称。 |
| `wheel_base` | `0.6` | 用于 Ackermann 转向换算的轴距。 |
| `ctrl_cmd_publish_rate_hz` | `50.0` | 保活控制指令发布频率。 |
| `cmd_vel_timeout_sec` | `0.3` | 超时后发布停车指令的等待时间。 |
| `max_velocity_mps` | `0.6` | 对底盘 SDK `/cmd_vel` 适配器生效的绝对速度硬限幅。 |
| `max_steering_deg` | `25.0` | 绝对转角限幅。 |
| `allow_reverse` | `false` | 未显式启用时拒绝倒车 `/cmd_vel` 指令。 |
| `use_stamped_cmd_vel` | `false` | 在 `input_topic` 上使用 `TwistStamped` 而不是 `Twist`。 |
| `forward_gear` | `4` | 前进和停车指令使用的挡位值。 |
| `reverse_gear` | `2` | 启用倒车时使用的挡位值。 |

## Nav2 指令行为

- 线速度 `x` 映射为目标底盘速度。
- 角速度 `z` 会结合配置的轴距换算为转向角。
- 当线速度接近 0 但角速度非 0 时，该指令会被忽略，因为 MK-mini 不能像差速底盘
  一样原地旋转。
- 如果在 `cmd_vel_timeout_sec` 内没有收到新指令，适配器会按
  `ctrl_cmd_publish_rate_hz` 持续发布零速度指令。
- 在 Jazzy 中，除非 Nav2 配置明确发布 `TwistStamped`，否则保持
  `use_stamped_cmd_vel=false`。
