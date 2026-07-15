from pathlib import Path
from types import SimpleNamespace
import unittest

from mkmini_neupan_bringup.thor_neupan_preflight_node import (
    CommandResult,
    CheckResult,
    build_preflight_launch_args,
    check_cvxpylayer_autograd,
    check_ctrl_cmd_publisher_count,
    check_neupan_config,
    check_node_conflicts,
    check_python_modules,
    check_required_topics,
    check_thor_runtime_manifest,
    check_topic_rate,
    has_cmd_vel_adapter_conflict,
    parse_average_rate,
    parse_publisher_count,
    TopicRateCheck,
)


class ThorNeuPANPreflightTest(unittest.TestCase):
    fixture_dir = Path(__file__).parent / "fixtures"

    def test_thor_runtime_manifest_accepts_exact_torch_version(self):
        results = check_thor_runtime_manifest(
            self.fixture_dir / "thor_runtime_valid.json",
            importer=lambda name: SimpleNamespace(
                __version__="2.8.0a0+5228986c39.nv25.04",
                version=SimpleNamespace(cuda="12.8"),
            ),
        )

        self.assertEqual(results, [CheckResult(
            "Thor runtime manifest",
            "PASS",
            "torch 2.8.0a0+5228986c39.nv25.04 matches runtime lock",
        )])

    def test_thor_runtime_manifest_rejects_missing_file(self):
        results = check_thor_runtime_manifest(self.fixture_dir / "missing.json")

        self.assertEqual(results[0].status, "FAIL")
        self.assertIn("does not exist", results[0].detail)

    def test_thor_runtime_manifest_rejects_placeholder_and_unset_version(self):
        for fixture in [
            "thor_runtime_null.json",
            "thor_runtime_empty.json",
            "thor_runtime_placeholder.json",
            "thor_runtime_unknown.json",
        ]:
            with self.subTest(fixture=fixture):
                results = check_thor_runtime_manifest(self.fixture_dir / fixture)

                self.assertEqual(results[0].status, "FAIL")
                self.assertIn("torch.__version__", results[0].detail)

    def test_thor_runtime_manifest_rejects_torch_version_mismatch(self):
        results = check_thor_runtime_manifest(
            self.fixture_dir / "thor_runtime_mismatch.json",
            importer=lambda name: SimpleNamespace(
                __version__="2.8.0a0+actual",
                version=SimpleNamespace(cuda="12.8"),
            ),
        )

        self.assertEqual(results[0].status, "FAIL")
        self.assertIn("expected 2.8.0a0+expected", results[0].detail)
        self.assertIn("found 2.8.0a0+actual", results[0].detail)

    def test_official_robot_config_validates_planner_and_checkpoint(self):
        from pathlib import Path

        robot = Path(__file__).parent / "fixtures" / "robot.yaml"

        results = check_neupan_config(robot)

        self.assertTrue(all(result.status == "PASS" for result in results))

    def test_python_module_check_reports_missing_module(self):
        def importer(module_name):
            if module_name == "cvxpylayers":
                raise ModuleNotFoundError("no cvxpylayers")
            if module_name == "torch":
                return SimpleNamespace(__version__="2.1.0")
            if module_name == "numpy":
                return SimpleNamespace(__version__="1.26.4")
            if module_name == "cvxpy":
                return SimpleNamespace(
                    __version__="1.5.3", installed_solvers=lambda: ["ECOS"]
                )
            return SimpleNamespace(__version__="1.2.3")

        results = check_python_modules(importer)
        failed = [result for result in results if result.failed]

        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].name, "Python module cvxpylayers")

    def test_python_runtime_rejects_numpy_two_and_missing_ecos(self):
        def importer(module_name):
            if module_name == "numpy":
                return SimpleNamespace(__version__="2.0.0")
            if module_name == "torch":
                return SimpleNamespace(__version__="2.1.0")
            if module_name == "cvxpy":
                return SimpleNamespace(
                    __version__="1.5.3", installed_solvers=lambda: ["SCS"]
                )
            return SimpleNamespace(__version__="1.2.3")

        results = check_python_modules(importer)
        failures = [result.detail for result in results if result.failed]

        self.assertTrue(any("numpy<2" in detail for detail in failures))
        self.assertTrue(any("ECOS" in detail for detail in failures))

    def test_python_runtime_rejects_old_torch(self):
        def importer(module_name):
            if module_name == "torch":
                return SimpleNamespace(__version__="2.0.1")
            if module_name == "numpy":
                return SimpleNamespace(__version__="1.26.4")
            if module_name == "cvxpy":
                return SimpleNamespace(
                    __version__="1.5.3", installed_solvers=lambda: ["ECOS"]
                )
            return SimpleNamespace(__version__="1.2.3")

        failures = [result.detail for result in check_python_modules(importer) if result.failed]

        self.assertTrue(any("torch>=2.1" in detail for detail in failures))

    def test_cvxpylayer_autograd_accepts_finite_expected_solution_and_gradient(self):
        result = check_cvxpylayer_autograd(
            smoke_test=lambda: (1.99999986, 3.9999995),
        )

        self.assertEqual(result.status, "PASS")
        self.assertIn("solution=2.000000", result.detail)
        self.assertIn("gradient=", result.detail)

    def test_cvxpylayer_autograd_reports_forward_or_backward_failure(self):
        def failing_smoke_test():
            raise RuntimeError("diffcp solve failed")

        result = check_cvxpylayer_autograd(smoke_test=failing_smoke_test)

        self.assertEqual(result.status, "FAIL")
        self.assertIn("diffcp solve failed", result.detail)

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
        self.assertIn("global planner", result.detail)

    def test_required_topics_are_pre_neupan_only(self):
        results = check_required_topics(
            {
                "/livox/lidar",
                "/livox/points",
                "/Odometry",
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
