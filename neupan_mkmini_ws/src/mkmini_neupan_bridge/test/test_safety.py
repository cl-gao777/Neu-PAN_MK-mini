import math
import unittest

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
        bridge = SafetyBridge(
            BridgeConfig(
                require_feedback=False,
                require_localization=True,
                localization_timeout_sec=0.3,
            )
        )
        bridge.set_drive_enabled(True, now_sec=9.0)
        bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=10.0
        )

        self.assertEqual(bridge.evaluate(10.1).reason, "localization_timeout")

        bridge.update_localization(healthy=False, now_sec=10.1)
        self.assertEqual(bridge.evaluate(10.2).reason, "localization_fault")

        bridge.update_localization(healthy=True, now_sec=10.1)
        self.assertEqual(bridge.evaluate(10.41).reason, "localization_timeout")

        bridge.update_localization(healthy=True, now_sec=10.42)
        bridge.update_command(
            AckermannCommand(speed_mps=0.2, steering_rad=0.1), now_sec=10.42
        )
        self.assertEqual(bridge.evaluate(10.43).reason, "active")

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
    def test_rejects_non_positive_safety_limits(self):
        invalid_configs = [
            dict(command_timeout_sec=0.0),
            dict(feedback_timeout_sec=-0.1),
            dict(localization_timeout_sec=0.0),
            dict(max_speed_mps=-0.3),
            dict(max_steering_deg=0.0),
        ]

        for values in invalid_configs:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    BridgeConfig(**values)

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
