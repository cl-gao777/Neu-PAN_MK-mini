import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mkmini_neupan_bridge.safety import (
    AckermannCommand,
    BridgeConfig,
    SafetyBridge,
)


class SafetyBridgeTest(unittest.TestCase):
    def setUp(self):
        self.bridge = SafetyBridge(
            BridgeConfig(
                command_timeout_sec=0.3,
                feedback_timeout_sec=0.5,
                min_drive_speed_mps=0.1,
                max_speed_mps=0.3,
                max_steering_deg=25.0,
                allow_reverse=False,
                forward_gear=4,
                reverse_gear=2,
                require_feedback=True,
            )
        )
        self.bridge.set_drive_enabled(True, now_sec=9.0)
        self.bridge.update_feedback(healthy=True, now_sec=10.0)

    def test_clamps_forward_speed_and_steering(self):
        self.bridge.update_command(
            AckermannCommand(speed_mps=0.8, steering_rad=math.radians(40.0)),
            now_sec=10.0,
        )

        decision = self.bridge.evaluate(now_sec=10.1)

        self.assertEqual(decision.reason, "active")
        self.assertEqual(decision.command.gear, 4)
        self.assertAlmostEqual(decision.command.velocity_mps, 0.3)
        self.assertAlmostEqual(decision.command.steering_deg, 25.0)

    def test_forward_speed_uses_configured_minimum_and_maximum(self):
        cases = [
            (0.0, 0.0),
            (0.1, 0.5),
            (0.5, 0.5),
            (0.55, 0.55),
            (0.6, 0.6),
            (0.7, 0.6),
        ]

        for requested_speed, expected_speed in cases:
            with self.subTest(requested_speed=requested_speed):
                bridge = SafetyBridge(
                    BridgeConfig(
                        min_drive_speed_mps=0.5,
                        max_speed_mps=0.6,
                        require_feedback=False,
                    )
                )
                bridge.set_drive_enabled(True, now_sec=9.0)
                bridge.update_command(
                    AckermannCommand(speed_mps=requested_speed, steering_rad=0.0),
                    now_sec=10.0,
                )

                decision = bridge.evaluate(now_sec=10.1)

                self.assertEqual(decision.reason, "active")
                self.assertAlmostEqual(decision.command.velocity_mps, expected_speed)

    def test_disallowed_reverse_produces_stop(self):
        self.bridge.update_command(
            AckermannCommand(speed_mps=-0.2, steering_rad=0.1),
            now_sec=10.0,
        )

        decision = self.bridge.evaluate(now_sec=10.1)

        self.assertEqual(decision.reason, "reverse_disallowed")
        self.assertEqual(decision.command.velocity_mps, 0.0)
        self.assertEqual(decision.command.steering_deg, 0.0)

    def test_reverse_uses_reverse_gear_when_enabled(self):
        bridge = SafetyBridge(
            BridgeConfig(
                allow_reverse=True,
                min_drive_speed_mps=0.1,
                require_feedback=False,
                forward_gear=4,
                reverse_gear=2,
            )
        )
        bridge.set_drive_enabled(True, now_sec=9.0)
        bridge.update_command(
            AckermannCommand(speed_mps=-0.2, steering_rad=-0.1),
            now_sec=10.0,
        )

        decision = bridge.evaluate(now_sec=10.1)

        self.assertEqual(decision.reason, "active")
        self.assertEqual(decision.command.gear, 2)
        self.assertAlmostEqual(decision.command.velocity_mps, 0.2)
        self.assertAlmostEqual(decision.command.steering_deg, math.degrees(-0.1))

    def test_safety_conditions_produce_stop(self):
        scenarios = [
            (lambda item: item.set_drive_enabled(False, 10.05), 10.1, "drive_disabled"),
            (lambda item: item.set_emergency_stop(True, 10.05), 10.1, "emergency_stop"),
            (lambda item: None, 10.31, "command_timeout"),
            (lambda item: item.update_feedback(False, 10.0), 10.1, "feedback_fault"),
            (lambda item: None, 10.51, "feedback_timeout"),
        ]

        for setup, now_sec, reason in scenarios:
            with self.subTest(reason=reason):
                self.setUp()
                self.bridge.update_command(
                    AckermannCommand(speed_mps=0.2, steering_rad=0.1), 10.0
                )
                setup(self.bridge)

                decision = self.bridge.evaluate(now_sec=now_sec)

                self.assertEqual(decision.reason, reason)
                self.assertEqual(decision.command.velocity_mps, 0.0)
                self.assertEqual(decision.command.steering_deg, 0.0)

    def test_required_localization_gates_motion(self):
        def armed_bridge():
            bridge = SafetyBridge(
                BridgeConfig(
                    require_feedback=False,
                    require_localization=True,
                    localization_timeout_sec=0.3,
                )
            )
            bridge.set_drive_enabled(True, now_sec=9.0)
            bridge.update_command(
                AckermannCommand(speed_mps=0.5, steering_rad=0.1), now_sec=10.0
            )
            return bridge

        bridge = armed_bridge()
        self.assertEqual(bridge.evaluate(10.1).reason, "localization_timeout")

        bridge = armed_bridge()
        bridge.update_localization(healthy=False, now_sec=10.1)
        self.assertEqual(bridge.evaluate(10.2).reason, "localization_fault")

        bridge = armed_bridge()
        bridge.update_localization(healthy=True, now_sec=10.1)
        self.assertEqual(bridge.evaluate(10.41).reason, "localization_timeout")

        bridge = armed_bridge()
        bridge.update_localization(healthy=True, now_sec=10.0)
        bridge.update_command(
            AckermannCommand(speed_mps=0.5, steering_rad=0.1), now_sec=10.01
        )
        self.assertEqual(bridge.evaluate(10.02).reason, "active")

    def test_feedback_and_localization_safety_faults_latch_until_rearm(self):
        scenarios = [
            (
                "feedback_fault",
                BridgeConfig(require_feedback=True),
                lambda bridge: bridge.update_feedback(False, 10.1),
                10.2,
                lambda bridge, now: bridge.update_feedback(True, now),
            ),
            (
                "feedback_timeout",
                BridgeConfig(require_feedback=True),
                lambda bridge: None,
                10.6,
                lambda bridge, now: bridge.update_feedback(True, now),
            ),
            (
                "feedback_time_invalid",
                BridgeConfig(require_feedback=True),
                lambda bridge: bridge.update_feedback(True, 11.0),
                10.2,
                lambda bridge, now: bridge.update_feedback(True, now),
            ),
            (
                "localization_fault",
                BridgeConfig(require_feedback=False, require_localization=True),
                lambda bridge: bridge.update_localization(False, 10.1),
                10.2,
                lambda bridge, now: bridge.update_localization(True, now),
            ),
            (
                "localization_timeout",
                BridgeConfig(require_feedback=False, require_localization=True),
                lambda bridge: None,
                10.4,
                lambda bridge, now: bridge.update_localization(True, now),
            ),
            (
                "localization_time_invalid",
                BridgeConfig(require_feedback=False, require_localization=True),
                lambda bridge: bridge.update_localization(True, 11.0),
                10.2,
                lambda bridge, now: bridge.update_localization(True, now),
            ),
        ]

        for reason, config, induce_fault, fault_time, recover in scenarios:
            with self.subTest(reason=reason):
                bridge = SafetyBridge(config)
                bridge.set_drive_enabled(True, now_sec=9.0)
                bridge.update_feedback(True, now_sec=10.0)
                bridge.update_localization(True, now_sec=10.0)
                bridge.update_command(
                    AckermannCommand(speed_mps=0.5, steering_rad=0.0),
                    now_sec=10.0,
                )
                induce_fault(bridge)

                self.assertEqual(bridge.evaluate(fault_time).reason, reason)

                recover(bridge, 12.0)
                bridge.update_command(
                    AckermannCommand(speed_mps=0.5, steering_rad=0.0),
                    now_sec=12.0,
                )
                self.assertEqual(bridge.evaluate(12.01).reason, reason)

                bridge.set_drive_enabled(False, now_sec=12.1)
                self.assertEqual(bridge.evaluate(12.11).reason, "drive_disabled")
                bridge.set_drive_enabled(True, now_sec=12.2)
                bridge.update_command(
                    AckermannCommand(speed_mps=0.5, steering_rad=0.0),
                    now_sec=12.2,
                )
                self.assertEqual(
                    bridge.evaluate(12.21).reason, "awaiting_fresh_command"
                )

                recover(bridge, 12.22)
                bridge.update_command(
                    AckermannCommand(speed_mps=0.5, steering_rad=0.0),
                    now_sec=12.22,
                )
                self.assertEqual(bridge.evaluate(12.23).reason, "active")

    def test_non_finite_command_produces_stop(self):
        commands = [
            AckermannCommand(speed_mps=math.nan, steering_rad=0.0),
            AckermannCommand(speed_mps=0.1, steering_rad=math.inf),
        ]

        for command in commands:
            with self.subTest(command=command):
                self.bridge.update_command(command, now_sec=10.0)

                decision = self.bridge.evaluate(now_sec=10.1)

                self.assertEqual(decision.reason, "invalid_command")
                self.assertEqual(decision.command.velocity_mps, 0.0)

    def test_no_command_produces_stop(self):
        bridge = SafetyBridge(BridgeConfig(require_feedback=False, forward_gear=4))
        bridge.set_drive_enabled(True, now_sec=9.0)

        decision = bridge.evaluate(now_sec=10.0)

        self.assertEqual(decision.reason, "no_command")
        self.assertEqual(decision.command.gear, 4)
        self.assertEqual(decision.command.velocity_mps, 0.0)

    def test_rearming_requires_a_new_command(self):
        self.bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=10.0
        )
        self.bridge.set_drive_enabled(False, now_sec=10.05)
        self.bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=10.1
        )
        self.bridge.set_drive_enabled(True, now_sec=10.2)

        decision = self.bridge.evaluate(now_sec=10.21)

        self.assertEqual(decision.reason, "awaiting_fresh_command")
        self.assertEqual(decision.command.velocity_mps, 0.0)

        self.bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=10.22
        )
        decision = self.bridge.evaluate(now_sec=10.23)
        self.assertEqual(decision.reason, "active")

    def test_command_at_same_timestamp_as_rearm_is_not_fresh(self):
        self.bridge.set_drive_enabled(False, now_sec=10.0)
        self.bridge.set_drive_enabled(True, now_sec=10.1)
        self.bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=10.1
        )

        decision = self.bridge.evaluate(now_sec=10.11)

        self.assertEqual(decision.reason, "awaiting_fresh_command")
        self.assertEqual(decision.command.velocity_mps, 0.0)

    def test_repeated_arm_does_not_make_existing_fresh_command_stale(self):
        self.bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=10.1
        )
        self.bridge.set_drive_enabled(True, now_sec=10.2)

        decision = self.bridge.evaluate(now_sec=10.21)

        self.assertEqual(decision.reason, "active")
        self.assertAlmostEqual(decision.command.velocity_mps, 0.2)

    def test_repeated_emergency_clear_does_not_make_existing_fresh_command_stale(self):
        self.bridge.set_emergency_stop(True, now_sec=10.0)
        self.bridge.set_emergency_stop(False, now_sec=10.1)
        self.bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=10.2
        )
        self.bridge.set_emergency_stop(False, now_sec=10.25)

        decision = self.bridge.evaluate(now_sec=10.26)

        self.assertEqual(decision.reason, "active")
        self.assertAlmostEqual(decision.command.velocity_mps, 0.2)

    def test_future_command_timestamp_produces_stop(self):
        self.bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=11.0
        )

        decision = self.bridge.evaluate(now_sec=10.1)

        self.assertEqual(decision.reason, "command_time_invalid")
        self.assertEqual(decision.command.velocity_mps, 0.0)

    def test_future_feedback_timestamp_produces_stop(self):
        self.bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=10.0
        )
        self.bridge.update_feedback(healthy=True, now_sec=11.0)

        decision = self.bridge.evaluate(now_sec=10.1)

        self.assertEqual(decision.reason, "feedback_time_invalid")
        self.assertEqual(decision.command.velocity_mps, 0.0)

    def test_non_finite_command_timestamp_produces_stop(self):
        self.bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=math.nan
        )

        decision = self.bridge.evaluate(now_sec=10.1)

        self.assertEqual(decision.reason, "command_time_invalid")
        self.assertEqual(decision.command.velocity_mps, 0.0)

    def test_non_finite_feedback_timestamp_produces_stop(self):
        self.bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=10.0
        )
        self.bridge.update_feedback(healthy=True, now_sec=math.nan)

        decision = self.bridge.evaluate(now_sec=10.1)

        self.assertEqual(decision.reason, "feedback_time_invalid")
        self.assertEqual(decision.command.velocity_mps, 0.0)


class BridgeConfigTest(unittest.TestCase):
    def test_default_drive_speed_window_matches_robot_policy(self):
        config = BridgeConfig()

        self.assertEqual(config.min_drive_speed_mps, 0.5)
        self.assertEqual(config.max_speed_mps, 0.6)

    def test_rejects_non_positive_safety_limits(self):
        invalid_configs = [
            dict(command_timeout_sec=0.0),
            dict(feedback_timeout_sec=-0.1),
            dict(localization_timeout_sec=0.0),
            dict(min_drive_speed_mps=0.0),
            dict(min_drive_speed_mps=math.nan),
            dict(max_speed_mps=-0.3),
            dict(max_steering_deg=0.0),
        ]

        for values in invalid_configs:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    BridgeConfig(**values)

    def test_rejects_minimum_drive_speed_above_maximum(self):
        with self.assertRaisesRegex(
            ValueError, "min_drive_speed_mps must not exceed max_speed_mps"
        ):
            BridgeConfig(min_drive_speed_mps=0.7, max_speed_mps=0.6)

    def test_rejects_out_of_range_gears(self):
        for values in [
            dict(forward_gear=-1),
            dict(reverse_gear=256),
            dict(forward_gear=4.5),
            dict(reverse_gear=True),
        ]:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    BridgeConfig(**values)


if __name__ == "__main__":
    unittest.main()
