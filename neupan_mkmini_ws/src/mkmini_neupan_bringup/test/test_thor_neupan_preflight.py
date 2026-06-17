from types import SimpleNamespace
import unittest

from mkmini_neupan_bringup.thor_neupan_preflight_node import (
    CHECKPOINT_PLACEHOLDER,
    CommandResult,
    CheckResult,
    build_preflight_launch_args,
    check_ctrl_cmd_publisher_count,
    check_neupan_config_contents,
    check_node_conflicts,
    check_python_modules,
    check_required_topics,
    check_topic_rate,
    extract_dune_checkpoint,
    has_cmd_vel_adapter_conflict,
    parse_average_rate,
    parse_publisher_count,
    TopicRateCheck,
)


class ThorNeuPANPreflightTest(unittest.TestCase):
    def test_extract_dune_checkpoint_from_pan_block(self):
        config = """
robot:
  wheelbase: 0.6
pan:
  iter_num: 2
  dune_checkpoint: /models/mkmini/model_5000.pth
adjust:
  solver: ECOS
"""

        self.assertEqual(
            extract_dune_checkpoint(config),
            "/models/mkmini/model_5000.pth",
        )

    def test_checkpoint_placeholder_is_hard_failure(self):
        results = check_neupan_config_contents(
            "pan:\n"
            f"  dune_checkpoint: {CHECKPOINT_PLACEHOLDER}\n"
        )

        self.assertEqual(results[0].status, "FAIL")
        self.assertIn("placeholder", results[0].detail)

    def test_missing_checkpoint_file_is_hard_failure(self):
        results = check_neupan_config_contents(
            "pan:\n"
            "  dune_checkpoint: /missing/model_5000.pth\n",
            checkpoint_exists=lambda path: False,
        )

        self.assertEqual(results[0].status, "FAIL")
        self.assertIn("does not exist", results[0].detail)

    def test_existing_checkpoint_file_passes(self):
        results = check_neupan_config_contents(
            "pan:\n"
            "  dune_checkpoint: /models/model_5000.pth\n",
            checkpoint_exists=lambda path: True,
        )

        self.assertEqual(results[0].status, "PASS")

    def test_python_module_check_reports_missing_module(self):
        def importer(module_name):
            if module_name == "cvxpylayers":
                raise ModuleNotFoundError("no cvxpylayers")
            return SimpleNamespace(__version__="1.2.3")

        results = check_python_modules(importer)
        failed = [result for result in results if result.failed]

        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].name, "Python module cvxpylayers")

    def test_parse_ctrl_cmd_publisher_count(self):
        self.assertEqual(parse_publisher_count("Publisher count: 1\n"), 1)
        self.assertEqual(parse_publisher_count("Publisher count: 12\n"), 12)
        self.assertIsNone(parse_publisher_count("Type: yhs_can_interfaces/CtrlCmd"))

    def test_ctrl_cmd_publisher_count_must_be_exactly_one(self):
        def runner(command, timeout):
            return CommandResult(command, 0, stdout="Publisher count: 2\n")

        result = check_ctrl_cmd_publisher_count(runner)

        self.assertEqual(result.status, "FAIL")
        self.assertIn("expected exactly 1", result.detail)

    def test_node_conflict_detects_vendor_cmd_vel_adapter(self):
        self.assertTrue(
            has_cmd_vel_adapter_conflict(
                "/ackermann_safety_bridge\n/cmd_vel_to_ctrl_cmd_node\n"
            )
        )

        def runner(command, timeout):
            return CommandResult(
                command,
                0,
                stdout="/ackermann_safety_bridge\n/cmd_vel_to_ctrl_cmd_node\n",
            )

        result = check_node_conflicts(runner)

        self.assertEqual(result.status, "FAIL")
        self.assertIn("vendor", result.detail)

    def test_parse_average_rate_uses_latest_average(self):
        output = "average rate: 8.1\naverage rate: 10.2\n"

        self.assertEqual(parse_average_rate(output), 10.2)

    def test_topic_rate_fails_when_average_is_too_low(self):
        def runner(command, timeout):
            return CommandResult(command, 0, stdout="average rate: 4.9\n")

        result = check_topic_rate(TopicRateCheck("/scan", 5.0, 8.0), runner)

        self.assertEqual(result.status, "FAIL")
        self.assertIn("4.90 Hz", result.detail)

    def test_topic_rate_timeout_with_average_can_pass(self):
        def runner(command, timeout):
            return CommandResult(
                command,
                124,
                stdout="average rate: 10.5\n",
                timed_out=True,
            )

        result = check_topic_rate(TopicRateCheck("/scan", 5.0, 8.0), runner)

        self.assertEqual(result.status, "PASS")
        self.assertIn("10.50 Hz", result.detail)

    def test_topic_rate_timeout_with_low_average_fails_on_rate(self):
        def runner(command, timeout):
            return CommandResult(
                command,
                124,
                stdout="average rate: 4.9\n",
                timed_out=True,
            )

        result = check_topic_rate(TopicRateCheck("/scan", 5.0, 8.0), runner)

        self.assertEqual(result.status, "FAIL")
        self.assertIn("4.90 Hz", result.detail)

    def test_topic_rate_timeout_mentions_plan_goal_when_relevant(self):
        def runner(command, timeout):
            return CommandResult(command, 124, timed_out=True)

        result = check_topic_rate(TopicRateCheck("/plan", 0.1, 20.0), runner)

        self.assertEqual(result.status, "FAIL")
        self.assertIn("Nav2", result.detail)

    def test_required_topics_are_pre_neupan_only(self):
        results = check_required_topics(
            {
                "/livox/lidar",
                "/livox/points",
                "/odom",
                "/scan",
                "/plan",
                "/chassis_info_fb",
                "/veh_diag_fb",
                "/ctrl_cmd",
            }
        )
        names = {result.name for result in results}

        self.assertNotIn("Topic /neupan_cmd_vel", names)
        self.assertNotIn("Topic /neupan/ackermann_cmd", names)
        self.assertTrue(all(result.status == "PASS" for result in results))

    def test_preflight_launch_args_force_neupan_off(self):
        launch_args, results = build_preflight_launch_args(
            ["start_scan_pipeline:=true", "start_neupan:=true"],
            None,
        )

        self.assertIn("start_scan_pipeline:=true", launch_args)
        self.assertEqual(launch_args[-1], "start_neupan:=false")
        self.assertEqual(results, [CheckResult(
            "Launch argument start_neupan",
            "WARN",
            "overriding user value to false for preflight",
        )])


if __name__ == "__main__":
    unittest.main()
