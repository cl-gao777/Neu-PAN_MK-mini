from dataclasses import dataclass
import math


@dataclass(frozen=True)
class AckermannCommand:
    speed_mps: float
    steering_rad: float


@dataclass(frozen=True)
class CtrlCommand:
    gear: int
    velocity_mps: float
    steering_deg: float


@dataclass(frozen=True)
class BridgeDecision:
    command: CtrlCommand
    reason: str


@dataclass(frozen=True)
class BridgeConfig:
    command_timeout_sec: float = 0.3
    feedback_timeout_sec: float = 0.5
    localization_timeout_sec: float = 0.3
    max_speed_mps: float = 0.3
    max_steering_deg: float = 25.0
    allow_reverse: bool = False
    forward_gear: int = 4
    reverse_gear: int = 2
    require_feedback: bool = True
    require_localization: bool = False

    def __post_init__(self) -> None:
        positive_values = {
            "command_timeout_sec": self.command_timeout_sec,
            "feedback_timeout_sec": self.feedback_timeout_sec,
            "localization_timeout_sec": self.localization_timeout_sec,
            "max_speed_mps": self.max_speed_mps,
            "max_steering_deg": self.max_steering_deg,
        }
        for name, value in positive_values.items():
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and greater than zero")

        for name, value in {
            "forward_gear": self.forward_gear,
            "reverse_gear": self.reverse_gear,
        }.items():
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
                raise ValueError(f"{name} must be an integer in [0, 255]")


class SafetyBridge:
    def __init__(self, config: BridgeConfig):
        self.config = config
        self._drive_enabled = False
        self._drive_enabled_since = None
        self._emergency_stop = False
        self._emergency_cleared_since = None
        self._feedback_healthy = False
        self._feedback_time_sec = None
        self._localization_healthy = False
        self._localization_time_sec = None
        self._command = None
        self._command_time_sec = None

    def set_drive_enabled(self, enabled: bool, now_sec: float) -> None:
        was_enabled = self._drive_enabled
        self._drive_enabled = enabled
        if enabled and not was_enabled:
            self._drive_enabled_since = now_sec

    def set_emergency_stop(self, active: bool, now_sec: float) -> None:
        was_active = self._emergency_stop
        self._emergency_stop = active
        if not active and was_active:
            self._emergency_cleared_since = now_sec

    def update_feedback(self, healthy: bool, now_sec: float) -> None:
        self._feedback_healthy = healthy
        self._feedback_time_sec = now_sec

    def update_command(self, command: AckermannCommand, now_sec: float) -> None:
        self._command = command
        self._command_time_sec = now_sec

    def update_localization(self, healthy: bool, now_sec: float) -> None:
        self._localization_healthy = healthy
        self._localization_time_sec = now_sec

    def evaluate(self, now_sec: float) -> BridgeDecision:
        if self._emergency_stop:
            return self._stop("emergency_stop")
        if not self._drive_enabled:
            return self._stop("drive_disabled")
        if self.config.require_feedback:
            if self._feedback_time_sec is None:
                return self._stop("feedback_timeout")
            if not self._feedback_healthy:
                return self._stop("feedback_fault")
            feedback_age = now_sec - self._feedback_time_sec
            if not math.isfinite(feedback_age) or feedback_age < 0.0:
                return self._stop("feedback_time_invalid")
            if feedback_age > self.config.feedback_timeout_sec:
                return self._stop("feedback_timeout")
        if self.config.require_localization:
            if self._localization_time_sec is None:
                return self._stop("localization_timeout")
            if not self._localization_healthy:
                return self._stop("localization_fault")
            localization_age = now_sec - self._localization_time_sec
            if not math.isfinite(localization_age) or localization_age < 0.0:
                return self._stop("localization_time_invalid")
            if localization_age > self.config.localization_timeout_sec:
                return self._stop("localization_timeout")
        if self._command is None or self._command_time_sec is None:
            return self._stop("no_command")
        activation_times = [
            timestamp
            for timestamp in (self._drive_enabled_since, self._emergency_cleared_since)
            if timestamp is not None
        ]
        if activation_times and self._command_time_sec <= max(activation_times):
            return self._stop("awaiting_fresh_command")
        if not math.isfinite(self._command.speed_mps) or not math.isfinite(
            self._command.steering_rad
        ):
            return self._stop("invalid_command")
        command_age = now_sec - self._command_time_sec
        if not math.isfinite(command_age) or command_age < 0.0:
            return self._stop("command_time_invalid")
        if command_age > self.config.command_timeout_sec:
            return self._stop("command_timeout")
        if self._command.speed_mps < 0.0 and not self.config.allow_reverse:
            return self._stop("reverse_disallowed")

        gear = (
            self.config.reverse_gear
            if self._command.speed_mps < 0.0
            else self.config.forward_gear
        )
        speed = min(abs(self._command.speed_mps), self.config.max_speed_mps)
        steering = math.degrees(self._command.steering_rad)
        steering = max(-self.config.max_steering_deg, min(steering, self.config.max_steering_deg))
        return BridgeDecision(CtrlCommand(gear, speed, steering), "active")

    def _stop(self, reason: str) -> BridgeDecision:
        command = CtrlCommand(self.config.forward_gear, 0.0, 0.0)
        return BridgeDecision(command, reason)
