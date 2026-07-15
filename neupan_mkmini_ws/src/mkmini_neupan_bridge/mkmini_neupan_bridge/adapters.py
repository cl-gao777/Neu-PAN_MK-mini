import math

from .safety import AckermannCommand


def legacy_neupan_action_to_ackermann(
    speed_mps: float, steering_rad: float
) -> AckermannCommand:
    return AckermannCommand(speed_mps, steering_rad)


def chassis_feedback_is_healthy(
    *,
    fault_level: int,
    auto_can_ctrl: bool,
    eps_offline: bool,
    eps_fault: bool,
    eps_mosfet_overtemp: bool,
    eps_warning: bool,
    eps_not_working: bool,
    eps_overcurrent: bool,
    ehb_ecu_fault: bool,
    ehb_offline: bool,
    ehb_work_mode_fault: bool,
    ehb_enable_fault: bool,
    ehb_angle_fault: bool,
    ehb_overtemp: bool,
    ehb_power_fault: bool,
    ehb_sensor_fault: bool,
    ehb_motor_fault: bool,
    ehb_oil_pressure_sensor_fault: bool,
    ehb_oil_fault: bool,
    left_drive_mcu_fault: int,
    right_drive_mcu_fault: int,
    auxiliary_bms_offline: bool,
    auxiliary_scram: bool,
    remote_closed: bool,
    remote_offline: bool,
    require_auto_can_mode: bool,
) -> bool:
    if fault_level != 0 or left_drive_mcu_fault != 0 or right_drive_mcu_fault != 0:
        return False
    if any(
        (
            eps_offline,
            eps_fault,
            eps_mosfet_overtemp,
            eps_warning,
            eps_not_working,
            eps_overcurrent,
            ehb_ecu_fault,
            ehb_offline,
            ehb_work_mode_fault,
            ehb_enable_fault,
            ehb_angle_fault,
            ehb_overtemp,
            ehb_power_fault,
            ehb_sensor_fault,
            ehb_motor_fault,
            ehb_oil_pressure_sensor_fault,
            ehb_oil_fault,
            auxiliary_bms_offline,
            auxiliary_scram,
            remote_closed,
            remote_offline,
        )
    ):
        return False
    return auto_can_ctrl or not require_auto_can_mode


def timer_period_from_rate(rate_hz: float) -> float:
    if not math.isfinite(rate_hz) or rate_hz <= 0.0:
        raise ValueError("publish_rate_hz must be finite and greater than zero")
    return 1.0 / rate_hz
