# MK-mini 官方使用说明摘录

本文档汇总厂家 Word 使用说明中的有用信息。它是本 SDK 的参考资料，不是 Thor
平台的最终运行目标说明。

## 来源范围

- 来源文档：原始桌面包中的厂家 MK-mini ROS 2 Word 使用说明。
- 厂家参考环境：Ubuntu 22.04、ROS 2 Humble、x86_64、PCAN。
- 当前 SDK 目标环境：Ubuntu 24.04、ROS 2 Jazzy、兼容 SocketCAN 的 `can4` 默认接口。

如果本文档与当前代码或 DBC 协议文件存在冲突，以当前代码和 DBC 为准。

## 厂家 CAN 配置

厂家文档将 CAN 接口配置为 `can0`，波特率为 500 kbit/s：

```bash
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up
```

厂家文档还建议安装 `can-utils`，并用以下命令检查底盘数据：

```bash
sudo apt-get install can-utils
candump can0
```

厂家示例保留了 `can0`，但当前 Thor + PEAK PCAN-USB 部署默认使用 `can4`。
现场应先用 `ip link` 确认接口名；如果不是 `can4`，请按实际接口名执行 CAN
命令并同步覆盖 `can_name`。

## 厂家 ROS 2 包结构

官方 ROS 2 包结构包含两个包：

- `yhs_can_control`：CAN 桥接和底盘控制节点。
- `yhs_can_interfaces`：自定义 ROS 2 消息定义。

当前 SDK 保留这些包名，使现有 launch 文件、话题名和消息导入方式保持一致。

## 厂家话题与消息

厂家文档描述了以下主要话题：

| 话题 | 消息 | 方向 | 说明 |
| --- | --- | --- | --- |
| `/ctrl_cmd` | `yhs_can_interfaces/msg/CtrlCmd` | 订阅 | 底盘运动指令。 |
| `/io_cmd` | `yhs_can_interfaces/msg/IoCmd` | 订阅 | 灯光、喇叭、放电和 IO 指令。 |
| `/chassis_info_fb` | `yhs_can_interfaces/msg/ChassisInfoFb` | 发布 | 聚合后的底盘反馈。 |
| `/veh_diag_fb` | `yhs_can_interfaces/msg/VehDiagFb` | 发布 | 专用整车诊断反馈，仅随诊断扩展 CAN 帧更新。 |

当前 SDK 保留这些接口，并新增面向 Nav2 的 `/cmd_vel`、`/odom`、专用 `/veh_diag_fb`
和可选 odom TF 发布。

## 官方字段说明摘录

厂家文档列出了以下重要字段含义：

- `CtrlCmd`
  - `ctrl_cmd_gear`：驱动挡位。
  - `ctrl_cmd_velocity`：目标速度。
  - `ctrl_cmd_steering`：目标转向角。
- `IoCmd`
  - `io_cmd_enable`：IO 指令使能。
  - `io_cmd_lower_beam_headlamp`：近光灯。
  - `io_cmd_upper_beam_headlamp`：远光灯。
  - `io_cmd_turn_lamp`：转向灯状态。
  - `io_cmd_braking_lamp`：刹车灯。
  - `io_cmd_clearance_lamp`：示廓灯。
  - `io_cmd_fog_lamp`：雾灯。
  - `io_cmd_speaker`：喇叭。
  - `io_cmd_dis_charge`：放电控制。
- `ChassisInfoFb`
  - `ctrl_fb`：控制反馈，包括挡位、速度、转角和模式。
  - `io_fb`：IO 反馈。
  - `lr_wheel_fb`、`rr_wheel_fb`：后轮速度和脉冲反馈。
  - `bms_flag_info_fb`、`bms_info_fb`：BMS 状态和标志位。
  - `drive_mcu_ecode_fb`：驱动 MCU 错误码。
  - `veh_diag_fb`：聚合消息中的最近一次底盘诊断位。安全桥诊断新鲜度使用专用 `/veh_diag_fb`。
  - `ultrasonic`：超声波距离反馈。

## 本 SDK 的差异

- 官方文档面向 Humble；本 SDK 面向 Jazzy。
- 官方文档主要说明直接发布 `/ctrl_cmd`；本 SDK 新增用于 Nav2 的 `/cmd_vel` 适配器。
- 官方文档提到用 `rqt_publisher` 手动测试；本 SDK 还补充了 `ros2 topic pub`、
  `/odom`、TF 和超时停车检查。
- 当前默认控制指令保活频率为 50 Hz，来源于
  `cmd_vel_to_ctrl_cmd_node.ctrl_cmd_publish_rate_hz`。
- Ubuntu 24.04 部署时应优先使用 systemd、netplan 或 systemd-networkd，而不是
  `rc.local`。
