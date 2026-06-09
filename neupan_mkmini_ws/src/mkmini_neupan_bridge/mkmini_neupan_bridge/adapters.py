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
    auxiliary_scram: bool,
    eps_fault: bool,
    require_auto_can_mode: bool,
) -> bool:
    if fault_level != 0 or auxiliary_scram or eps_fault:
        return False
    return auto_can_ctrl or not require_auto_can_mode


def timer_period_from_rate(rate_hz: float) -> float:
    if not math.isfinite(rate_hz) or rate_hz <= 0.0:
        raise ValueError("publish_rate_hz must be finite and greater than zero")
    return 1.0 / rate_hz
