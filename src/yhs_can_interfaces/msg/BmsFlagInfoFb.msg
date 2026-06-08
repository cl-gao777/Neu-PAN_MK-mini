# BMS 电池保护板状态位反馈。
uint8 bms_flag_info_soc                  # 电池剩余电量百分比。
bool bms_flag_info_single_ov             # 单体过压。
bool bms_flag_info_single_uv             # 单体欠压。
bool bms_flag_info_ov                    # 总压过压。
bool bms_flag_info_uv                    # 总压欠压。
bool bms_flag_info_charge_ot             # 充电过温。
bool bms_flag_info_charge_ut             # 充电低温。
bool bms_flag_info_discharge_ot          # 放电过温。
bool bms_flag_info_discharge_ut          # 放电低温。
bool bms_flag_info_charge_oc             # 充电过流。
bool bms_flag_info_discharge_oc          # 放电过流。
bool bms_flag_info_short                 # 短路故障。
bool bms_flag_info_ic_error              # BMS 芯片或采样异常。
bool bms_flag_info_lock_mos              # MOS 管锁定保护。
bool bms_flag_info_charge_flag           # 充电状态标志。
bool bms_flag_info_soc_warning           # 电量告警。
bool bms_flag_info_soc_low_protection    # 低电量保护。
float32 bms_flag_info_hight_temperature  # 最高温度，单位摄氏度；字段名沿用厂家拼写。
float32 bms_flag_info_low_temperature    # 最低温度，单位摄氏度。
