# 整车诊断反馈。字段较多，均来自厂家诊断 CAN 帧。
uint8 veh_fb_fault_level                 # 整车故障等级。
bool veh_fb_auto_can_ctrl_cmd            # 自动驾驶 CAN 控制指令状态。
bool veh_fb_auto_io_can_cmd              # 自动驾驶 IO CAN 指令状态。

bool veh_fb_eps_dis_on_line              # EPS 离线。
bool veh_fb_eps_fault                    # EPS 故障。
bool veh_fb_eps_mosf_et_ot               # EPS MOSFET 过温；字段名沿用厂家拼写。
bool veh_fb_eps_warning                  # EPS 告警。
bool veh_fb_eps_dis_work                 # EPS 不工作。
bool veh_fb_eps_over_current             # EPS 过流。
bool veh_fb_st_reserve                   # 预留状态位。

bool veh_fb_ehb_ecu_fault                # EHB ECU 故障。
bool veh_fb_ehb_dis_on_line              # EHB 离线。
bool veh_fb_ehb_work_model_fault         # EHB 工作模式故障。
bool veh_fb_ehb_dis_en                   # EHB 使能异常。
bool veh_fb_ehb_anguler_fault            # EHB 角度故障；字段名沿用厂家拼写。
bool veh_fb_ehb_ot                       # EHB 过温。
bool veh_fb_ehb_power_fault              # EHB 电源故障。
bool veh_fb_ehb_sensor_abnomal           # EHB 传感器异常；字段名沿用厂家拼写。
bool veh_fb_ehb_motor_fault              # EHB 电机故障。
bool veh_fb_ehb_oil_press_sensor_fault   # EHB 油压传感器故障。
bool veh_fb_ehb_oil_fault                # EHB 油路故障。

uint8 veh_fb_ld_rv_mcu_fault             # 左驱动 MCU 故障位。
uint8 veh_fb_rd_rv_mcu_fault             # 右驱动 MCU 故障位。

bool veh_fb_aux_bms_dis_on_line          # 辅助 BMS 离线。
bool veh_fb_aux_scram                    # 辅助急停。
bool veh_fb_aux_remote_close             # 辅助遥控关闭。
bool veh_fb_aux_remote_dis_on_line       # 辅助遥控离线。
