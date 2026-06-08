# 底盘运动控制反馈。
uint8    ctrl_fb_gear      # 当前挡位。
float32  ctrl_fb_velocity  # 当前速度，单位 m/s。
float32  ctrl_fb_steering  # 当前转向角，单位 deg。
uint8    ctrl_fb_mode      # 当前控制模式，具体含义见厂家协议。
