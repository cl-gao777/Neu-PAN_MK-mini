import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mkmini_neupan_bridge.adapters import (
    chassis_feedback_is_healthy,
    legacy_neupan_action_to_ackermann,
    timer_period_from_rate,
)


HEALTHY_CHASSIS_FEEDBACK = {
    "fault_level": 0,
    "auto_can_ctrl": True,
    "eps_offline": False,
    "eps_fault": False,
    "eps_mosfet_overtemp": False,
    "eps_warning": False,
    "eps_not_working": False,
    "eps_overcurrent": False,
    "ehb_ecu_fault": False,
    "ehb_offline": False,
    "ehb_work_mode_fault": False,
    "ehb_enable_fault": False,
    "ehb_angle_fault": False,
    "ehb_overtemp": False,
    "ehb_power_fault": False,
    "ehb_sensor_fault": False,
    "ehb_motor_fault": False,
    "ehb_oil_pressure_sensor_fault": False,
    "ehb_oil_fault": False,
    "left_drive_mcu_fault": 0,
    "right_drive_mcu_fault": 0,
    "auxiliary_bms_offline": False,
    "auxiliary_scram": False,
    "remote_closed": False,
    "remote_offline": False,
}


class AdapterTest(unittest.TestCase):
    def test_legacy_neupan_action_preserves_acker_semantics(self):
        command = legacy_neupan_action_to_ackermann(0.25, -0.2)

        self.assertAlmostEqual(command.speed_mps, 0.25)
        self.assertAlmostEqual(command.steering_rad, -0.2)

    def test_feedback_requires_fault_free_auto_can_mode(self):
        self.assertTrue(
            chassis_feedback_is_healthy(
                **HEALTHY_CHASSIS_FEEDBACK,
                require_auto_can_mode=True,
            )
        )

        for field, unhealthy_value in {
            "fault_level": 1,
            "auto_can_ctrl": False,
            "eps_offline": True,
            "eps_fault": True,
            "eps_mosfet_overtemp": True,
            "eps_warning": True,
            "eps_not_working": True,
            "eps_overcurrent": True,
            "ehb_ecu_fault": True,
            "ehb_offline": True,
            "ehb_work_mode_fault": True,
            "ehb_enable_fault": True,
            "ehb_angle_fault": True,
            "ehb_overtemp": True,
            "ehb_power_fault": True,
            "ehb_sensor_fault": True,
            "ehb_motor_fault": True,
            "ehb_oil_pressure_sensor_fault": True,
            "ehb_oil_fault": True,
            "left_drive_mcu_fault": 1,
            "right_drive_mcu_fault": 1,
            "auxiliary_bms_offline": True,
            "auxiliary_scram": True,
            "remote_closed": True,
            "remote_offline": True,
        }.items():
            with self.subTest(field=field):
                feedback = {**HEALTHY_CHASSIS_FEEDBACK, field: unhealthy_value}
                self.assertFalse(
                    chassis_feedback_is_healthy(
                        **feedback, require_auto_can_mode=True
                    )
                )

    def test_feedback_can_ignore_auto_mode_during_bench_diagnostics(self):
        self.assertTrue(
            chassis_feedback_is_healthy(
                **{**HEALTHY_CHASSIS_FEEDBACK, "auto_can_ctrl": False},
                require_auto_can_mode=False,
            )
        )

    def test_timer_period_requires_positive_finite_rate(self):
        self.assertAlmostEqual(timer_period_from_rate(50.0), 0.02)

        for rate in [0.0, -1.0, math.nan, math.inf]:
            with self.subTest(rate=rate):
                with self.assertRaises(ValueError):
                    timer_period_from_rate(rate)


if __name__ == "__main__":
    unittest.main()
