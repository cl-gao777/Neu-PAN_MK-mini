# 底盘运动控制指令。通常由 cmd_vel_to_ctrl_cmd_node 从 /cmd_vel 转换得到。
# 官方档位枚举：00 disable, 01 P, 02 R, 03 N, 04 D。
uint8    ctrl_cmd_gear      # 目标档位；前进使用 D=4，倒车使用 R=2。
float32  ctrl_cmd_velocity  # 目标速度，单位 m/s；保持非负，倒车通过挡位表达。
float32  ctrl_cmd_steering  # 目标转向角，单位 deg。
