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


class AdapterTest(unittest.TestCase):
    def test_legacy_neupan_action_preserves_acker_semantics(self):
        command = legacy_neupan_action_to_ackermann(0.25, -0.2)

        self.assertAlmostEqual(command.speed_mps, 0.25)
        self.assertAlmostEqual(command.steering_rad, -0.2)

    def test_feedback_requires_fault_free_auto_can_mode(self):
        self.assertTrue(
            chassis_feedback_is_healthy(
                fault_level=0,
                auto_can_ctrl=True,
                auxiliary_scram=False,
                eps_fault=False,
                require_auto_can_mode=True,
            )
        )

        unhealthy_cases = [
            dict(fault_level=1, auto_can_ctrl=True, auxiliary_scram=False, eps_fault=False),
            dict(fault_level=0, auto_can_ctrl=False, auxiliary_scram=False, eps_fault=False),
            dict(fault_level=0, auto_can_ctrl=True, auxiliary_scram=True, eps_fault=False),
            dict(fault_level=0, auto_can_ctrl=True, auxiliary_scram=False, eps_fault=True),
        ]
        for case in unhealthy_cases:
            with self.subTest(case=case):
                self.assertFalse(
                    chassis_feedback_is_healthy(
                        **case,
                        require_auto_can_mode=True,
                    )
                )

    def test_feedback_can_ignore_auto_mode_during_bench_diagnostics(self):
        self.assertTrue(
            chassis_feedback_is_healthy(
                fault_level=0,
                auto_can_ctrl=False,
                auxiliary_scram=False,
                eps_fault=False,
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
