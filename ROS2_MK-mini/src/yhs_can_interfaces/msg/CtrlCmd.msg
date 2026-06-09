# 底盘运动控制指令。通常由 cmd_vel_to_ctrl_cmd_node 从 /cmd_vel 转换得到。
uint8    ctrl_cmd_gear      # 挡位；当前适配器默认前进 1、倒车 2。
float32  ctrl_cmd_velocity  # 目标速度，单位 m/s；保持非负，倒车通过挡位表达。
float32  ctrl_cmd_steering  # 目标转向角，单位 deg。
