# 聚合后的底盘反馈。驱动节点每解析到一个反馈帧，就更新对应子消息并发布本消息。
std_msgs/Header header

yhs_can_interfaces/CtrlFb     ctrl_fb              # 车辆控制反馈：挡位、速度、转角、模式。
yhs_can_interfaces/IoFb       io_fb                # 灯光、急停、碰撞传感器等 IO 反馈。
yhs_can_interfaces/LrWheelFb  lr_wheel_fb          # 左后轮速度和脉冲反馈。
yhs_can_interfaces/OdoFb      odo_fb               # 底盘累计里程和累计角度反馈。
yhs_can_interfaces/RrWheelFb  rr_wheel_fb          # 右后轮速度和脉冲反馈。
yhs_can_interfaces/BmsFlagInfoFb  bms_flag_info_fb # BMS 告警/保护状态位。
yhs_can_interfaces/BmsInfoFb      bms_info_fb      # BMS 电压、电流、容量。
yhs_can_interfaces/DriveMcuEcodeFb  drive_mcu_ecode_fb # 驱动 MCU 错误码。
yhs_can_interfaces/VehDiagFb      veh_diag_fb      # 整车诊断状态。
yhs_can_interfaces/Ultrasonic     ultrasonic       # 8 路超声波距离。
