# 底盘 IO 控制指令，用于灯光、喇叭、放电等辅助功能。
bool   io_cmd_enable                # IO 控制使能。
bool   io_cmd_lower_beam_headlamp   # 近光灯。
bool   io_cmd_upper_beam_headlamp   # 远光灯。
uint8  io_cmd_turn_lamp             # 转向灯状态，具体取值见厂家协议。
bool   io_cmd_braking_lamp          # 刹车灯。
bool   io_cmd_clearance_lamp        # 示廓灯。
bool   io_cmd_fog_lamp              # 雾灯。
bool   io_cmd_speaker               # 喇叭。
bool   io_cmd_dis_charge            # 放电控制。
