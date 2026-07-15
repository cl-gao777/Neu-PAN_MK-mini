# MK-mini 启动验收清单

在将 MK-mini 接入 Nav2 或运行自主导航前，请先按本清单检查。首次测试应架空车轮
或在受控测试区域内进行。

## 1. 上电前检查

- [ ] 车体机械状态稳定，车轮可以安全转动。
- [ ] 急停按钮触手可及，并已验证有效。
- [ ] CANH 和 CANL 已连接到适配器的正确端子。
- [ ] CAN 地线或参考线接法符合适配器和底盘接线说明。
- [ ] 电池电压和 BMS 状态适合测试。
- [ ] Thor 运行 Ubuntu 24.04 和 ROS 2 Jazzy。

## 2. CAN 接口检查

启动 CAN 接口：

```bash
sudo ip link set can4 down || true
sudo ip link set can4 type can bitrate 500000
sudo ip link set can4 up
ip -details link show can4
```

预期结果：

- [ ] `can4` 存在；如果 Thor 上接口名不同，已按 `ip link` 结果覆盖 `can_name`。
- [ ] 波特率为 `500000`。
- [ ] 接口状态为 `UP`。
- [ ] 没有反复出现 bus-off 或重启错误。

检查底盘原始 CAN 数据：

```bash
candump can4
```

预期结果：

- [ ] 底盘上电后能看到 CAN 帧。
- [ ] 反馈持续出现，没有长时间中断。
- [ ] 如果没有任何帧，请检查 CANH/CANL 极性、波特率、适配器驱动、底盘电源和急停状态。

## 3. 构建与启动检查

构建：

```bash
cd ~/ROS2_MK-mini
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

启动：

```bash
ros2 launch yhs_can_control yhs_can_control.launch.py
```

预期结果：

- [ ] `yhs_can_control_node` 正常启动。
- [ ] `cmd_vel_to_ctrl_cmd_node` 正常启动。
- [ ] 没有关于 `can4` 或实际 `can_name` 的致命错误。
- [ ] 没有关于 `ultrasonic_number` 的致命错误。

## 4. ROS 话题检查

在第二个终端中执行：

```bash
source /opt/ros/jazzy/setup.bash
source ~/ROS2_MK-mini/install/setup.bash
ros2 topic list
```

预期话题：

- [ ] `/ctrl_cmd`
- [ ] `/io_cmd`
- [ ] `/cmd_vel`
- [ ] `/chassis_info_fb`
- [ ] `/veh_diag_fb`
- [ ] `/odom`
- [ ] `/tf`

检查反馈：

```bash
ros2 topic echo /chassis_info_fb
ros2 topic echo /veh_diag_fb
ros2 topic hz /chassis_info_fb
ros2 topic hz /veh_diag_fb
```

预期结果：

- [ ] 存在 CAN 反馈时，反馈消息会持续更新。
- [ ] 当对应 CAN 帧存在时，`ctrl_fb`、车轮反馈、BMS、诊断和超声波字段有数据。
- [ ] `/veh_diag_fb` 只随整车诊断扩展帧更新，可用于判断诊断帧新鲜度。

检查里程计：

```bash
ros2 topic echo /odom
ros2 topic hz /odom
```

预期结果：

- [ ] 当底盘里程计或速度反馈可用时，`/odom` 会更新。
- [ ] `header.frame_id` 为 `odom`。
- [ ] `child_frame_id` 为 `base_link`。

如果启用了 TF，请检查：

```bash
ros2 run tf2_ros tf2_echo odom base_link
```

预期结果：

- [ ] 变换可用。
- [ ] 里程计更新时，变换也随之更新。

## 5. 架空车轮运动测试

保持车体架空或受限位约束。发送一次短暂低速指令：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
"{linear: {x: 0.5}, angular: {z: 0.0}}"
```

预期结果：

- [ ] 车轮以低速响应。
- [ ] `/ctrl_cmd` 短暂显示非零速度。
- [ ] 底盘反馈可用时，`/chassis_info_fb.ctrl_fb` 能反映运动状态。
- [ ] 超过 `cmd_vel_timeout_sec` 后，`/ctrl_cmd` 回到零速度。

检查转向：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
"{linear: {x: 0.5}, angular: {z: 0.1}}"
```

预期结果：

- [ ] 转向反馈按预期方向变化。
- [ ] 转向角保持在 `max_steering_deg` 范围内。

## 6. 安全检查

- [ ] 停车指令有效：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
"{linear: {x: 0.0}, angular: {z: 0.0}}"
```

- [ ] 指令超时有效：停止发布 `/cmd_vel`，确认超过 `cmd_vel_timeout_sec` 后持续发布零速度 `/ctrl_cmd`。
- [ ] 默认阻止倒车：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
"{linear: {x: -0.3}, angular: {z: 0.0}}"
```

预期结果：

- [ ] 当 `allow_reverse=false` 时，适配器发布停车指令，而不是倒车运动。
- [ ] 在完成架空车轮测试并具备受控测试区域前，不要启用倒车。

## 7. 低速地面测试

只有架空车轮检查通过后，才继续地面测试。

- [ ] 使用空旷、平整的测试区域。
- [ ] 初始地面测试速度使用实测可响应下限 `0.5 m/s`；底盘 SDK `/cmd_vel` 适配器硬限幅为 `0.6 m/s`，倒车保持禁用。
- [ ] 保持有人靠近急停按钮。
- [ ] 先发送短时 `/cmd_vel` 指令，不要直接进行连续导航。
- [ ] 确认 `/odom` 方向与实际运动一致。
- [ ] 确认转向符号符合 Nav2 预期行为。

## 8. Nav2 接入前检查

启用自主导航前：

- [ ] Nav2 发布的 `/cmd_vel` 类型与 `use_stamped_cmd_vel` 配置一致。
- [ ] `odom -> base_link` TF 只由一个来源提供，可以是本 SDK，也可以是其他里程计来源，但不能重复发布。
- [ ] Nav2 速度限幅不高于 SDK 限幅。
- [ ] 需要原地旋转的恢复行为已禁用或适配，因为 MK-mini 使用 Ackermann 风格转向，不能原地旋转。
- [ ] 在完整路线自主导航前，已使用低速度限幅测试局部规划器输出。

## 故障排查

| 现象 | 检查 | 可能原因 | 下一步 |
| --- | --- | --- | --- |
| 缺少 `can4` | `ip link` | 驱动或适配器未加载，或接口名不同 | 检查 USB/PCI 适配器、驱动和接口名称。 |
| `candump can4` 没有帧 | `candump can4` | 接线、波特率、底盘电源或急停问题 | 重新检查 CANH/CANL、500 kbit/s、电源和急停。 |
| launch 无法打开 CAN | launch 日志、`ip link` | `can4` 未启动或名称错误 | 启动 CAN，或设置 `can_name`。 |
| `/chassis_info_fb` 不更新 | `candump`、`ros2 topic echo` | 没有有效反馈帧，或校验失败被丢弃 | 确认原始 CAN 帧和协议版本。 |
| `/veh_diag_fb` 不更新 | `candump`、`ros2 topic hz /veh_diag_fb` | 整车诊断扩展帧缺失或未匹配 | 确认诊断 CAN ID 和扩展帧解析。 |
| `/odom` 不变化 | `/chassis_info_fb.ctrl_fb`、`/chassis_info_fb.odo_fb` | 没有里程计或速度反馈 | 确认反馈帧和车轮运动。 |
| 缺少 TF | `tf2_echo odom base_link` | `publish_odom_tf=false` 或 `/odom` 未更新 | 启用 `publish_odom_tf` 并检查 `/odom`。 |
| 车辆不倒车 | 适配器日志、参数 | `allow_reverse=false` | 仅在安全测试后启用。 |
