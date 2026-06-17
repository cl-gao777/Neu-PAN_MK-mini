from pathlib import Path
import unittest


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
MONOREPO_ROOT = WORKSPACE_ROOT.parent


class WorkspaceContractTest(unittest.TestCase):
    def test_stack_check_frequency_probe_has_a_timeout(self):
        script = (WORKSPACE_ROOT / "scripts" / "check_stack.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("timeout 6s ros2 topic hz", script)

    def test_scan_topic_launch_argument_is_remapped_into_slam_toolbox(self):
        launch_file = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "launch"
            / "perception_slam.launch.py"
        ).read_text(encoding="utf-8")

        self.assertIn('SetRemap(src="/scan", dst=scan_topic)', launch_file)

    def test_formal_and_bench_configs_use_expected_localization_gates(self):
        config_dir = (
            WORKSPACE_ROOT / "src" / "mkmini_neupan_bridge" / "config"
        )
        formal = (config_dir / "safety_bridge.yaml").read_text(encoding="utf-8")
        bench = (config_dir / "safety_bridge_bench.yaml").read_text(encoding="utf-8")

        self.assertIn("require_localization: true", formal)
        self.assertIn("require_localization: false", bench)
        self.assertIn("max_speed_mps: 0.3", bench)

    def test_safety_bridge_uses_dedicated_diagnostic_topic(self):
        config_dir = (
            WORKSPACE_ROOT / "src" / "mkmini_neupan_bridge" / "config"
        )
        formal = (config_dir / "safety_bridge.yaml").read_text(encoding="utf-8")
        bench = (config_dir / "safety_bridge_bench.yaml").read_text(encoding="utf-8")
        bridge_node = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bridge"
            / "mkmini_neupan_bridge"
            / "ackermann_safety_bridge_node.py"
        ).read_text(encoding="utf-8")
        can_node = (
            MONOREPO_ROOT
            / "ROS2_MK-mini"
            / "src"
            / "yhs_can_control"
            / "src"
            / "yhs_can_control_node.cpp"
        ).read_text(encoding="utf-8")

        for config in (formal, bench):
            with self.subTest(config=config[:40]):
                self.assertIn("diagnostic_topic: /veh_diag_fb", config)
                self.assertNotIn("feedback_topic:", config)
        self.assertIn("VehDiagFb", bridge_node)
        self.assertIn('"diagnostic_topic", "/veh_diag_fb"', bridge_node)
        self.assertIn("create_publisher<yhs_can_interfaces::msg::VehDiagFb>", can_node)
        self.assertIn("veh_diag_fb_publisher_->publish(msg)", can_node)

    def test_all_mkmini_control_configs_use_official_drive_gear(self):
        bridge_config = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bridge"
            / "config"
            / "safety_bridge.yaml"
        ).read_text(encoding="utf-8")
        bench_config = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bridge"
            / "config"
            / "safety_bridge_bench.yaml"
        ).read_text(encoding="utf-8")
        vendor_config = (
            MONOREPO_ROOT
            / "ROS2_MK-mini"
            / "src"
            / "yhs_can_control"
            / "params"
            / "cfg.yaml"
        ).read_text(encoding="utf-8")

        for config in (bridge_config, bench_config, vendor_config):
            with self.subTest(config=config[:40]):
                self.assertIn("forward_gear: 4", config)
                self.assertIn("reverse_gear: 2", config)

    def test_vendor_cmd_vel_adapter_default_limit_is_0_8_mps(self):
        vendor_config = (
            MONOREPO_ROOT
            / "ROS2_MK-mini"
            / "src"
            / "yhs_can_control"
            / "params"
            / "cfg.yaml"
        ).read_text(encoding="utf-8")

        self.assertIn("max_velocity_mps: 0.8", vendor_config)

    def test_ctrl_cmd_message_documents_official_gear_enum(self):
        message = (
            MONOREPO_ROOT
            / "ROS2_MK-mini"
            / "src"
            / "yhs_can_interfaces"
            / "msg"
            / "CtrlCmd.msg"
        ).read_text(encoding="utf-8")

        for expected in [
            "00 disable",
            "01 P",
            "02 R",
            "03 N",
            "04 D",
        ]:
            self.assertIn(expected, message)

    def test_full_stack_has_opt_in_neupan_launch(self):
        launch_file = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "launch"
            / "full_stack.launch.py"
        ).read_text(encoding="utf-8")

        self.assertIn('DeclareLaunchArgument("start_neupan", default_value="false")', launch_file)
        self.assertIn('"neupan.launch.py"', launch_file)
        self.assertIn("IfCondition(start_neupan)", launch_file)

    def test_neupan_launch_fails_fast_without_package_or_checkpoint(self):
        launch_file = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "launch"
            / "neupan.launch.py"
        ).read_text(encoding="utf-8")

        self.assertIn("get_package_share_directory", launch_file)
        self.assertIn("REPLACE_WITH_TRAINED_MKMINI_DUNE_CHECKPOINT", launch_file)
        self.assertIn("RuntimeError", launch_file)

    def test_full_stack_can_pass_custom_neupan_config_to_neupan_launch(self):
        launch_file = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "launch"
            / "full_stack.launch.py"
        ).read_text(encoding="utf-8")
        neupan_launch_file = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "launch"
            / "neupan.launch.py"
        ).read_text(encoding="utf-8")

        self.assertIn('DeclareLaunchArgument("neupan_config", default_value="")', launch_file)
        self.assertIn('"neupan_config": neupan_config', launch_file)
        self.assertIn('DeclareLaunchArgument("neupan_config", default_value=default_config)', neupan_launch_file)
        self.assertIn('if not config_path:', neupan_launch_file)

    def test_docker_test_runner_returns_failure_when_tests_fail(self):
        script = (
            MONOREPO_ROOT
            / "docker"
            / "scripts"
            / "run_tests.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("set -euo pipefail", script)
        self.assertIn("colcon test --packages-select yhs_can_interfaces yhs_can_control", script)
        self.assertIn("--return-code-on-test-failure", script)
        self.assertIn("colcon test-result --verbose", script)
        self.assertIn('python3 -m pytest "${test_dir}" -v', script)
        self.assertNotIn("--return-code-on-test-failure || true", script)
        self.assertNotIn("colcon test-result --verbose || true", script)
        self.assertNotIn('python3 -m pytest "${test_dir}" -v ||', script)
        self.assertNotIn("PASS=0", script)
        self.assertNotIn("FAIL=0", script)

    def test_stack_check_rejects_missing_neupan_frequency_and_duplicate_control_publishers(self):
        script = (WORKSPACE_ROOT / "scripts" / "check_stack.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn('timeout 6s ros2 topic hz "$topic" --window 50', script)
        self.assertNotIn("ros2 topic hz /neupan_cmd_vel --window 50 || true", script)
        self.assertIn("ros2 topic info /ctrl_cmd", script)
        self.assertIn("Publisher count: 1", script)
        self.assertIn("cmd_vel_to_ctrl_cmd_node", script)
        self.assertIn("/veh_diag_fb", script)
        self.assertIn("check_topic_hz /neupan_cmd_vel", script)
        self.assertIn("check_topic_hz /neupan/ackermann_cmd", script)
        self.assertIn("check_topic_hz /veh_diag_fb 2.0", script)
        self.assertIn("rate >= min_rate", script)

    def test_acceptance_recording_captures_dedicated_diagnostic_topic(self):
        script = (
            WORKSPACE_ROOT / "scripts" / "record_acceptance_run.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("/veh_diag_fb", script)

    def test_runtime_check_treats_missing_checkpoint_as_hard_failure(self):
        script = (WORKSPACE_ROOT / "scripts" / "check_neupan_runtime.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("REPLACE_WITH_TRAINED_MKMINI_DUNE_CHECKPOINT", script)
        self.assertIn("Train MK-mini DUNE", script)

    def test_import_upstreams_script_imports_all_required_sources(self):
        script = (WORKSPACE_ROOT / "scripts" / "import_upstreams.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("vcs import . < mkmini_neupan.repos", script)
        self.assertIn("bash scripts/freeze_revisions.sh", script)
        self.assertIn("src/neupan_ros2", script)
        self.assertIn("src/livox_ros_driver2", script)
        self.assertIn("src/FAST_LIO", script)
        self.assertIn("third_party/NeuPAN", script)
        self.assertIn("MKMINI_VENDOR_SRC", script)
        self.assertIn("src/yhs_can_control", script)
        self.assertIn("src/yhs_can_interfaces", script)

    def test_bootstrap_requires_imported_neupan_sources_before_build(self):
        script = (WORKSPACE_ROOT / "scripts" / "bootstrap_jazzy.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("src/neupan_ros2", script)
        self.assertIn("src/livox_ros_driver2", script)
        self.assertIn("src/FAST_LIO", script)
        self.assertIn("third_party/NeuPAN", script)
        self.assertIn("bash scripts/import_upstreams.sh /path/to/ROS2_MK-mini/src", script)


if __name__ == "__main__":
    unittest.main()
