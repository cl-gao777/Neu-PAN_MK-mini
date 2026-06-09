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
        self.assertIn("max_speed_mps: 0.1", bench)

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

    def test_stack_check_rejects_missing_neupan_frequency_and_duplicate_control_publishers(self):
        script = (WORKSPACE_ROOT / "scripts" / "check_stack.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn('timeout 6s ros2 topic hz "$topic" --window 50', script)
        self.assertNotIn("ros2 topic hz /neupan_cmd_vel --window 50 || true", script)
        self.assertIn("ros2 topic info /ctrl_cmd", script)
        self.assertIn("Publisher count: 1", script)
        self.assertIn("cmd_vel_to_ctrl_cmd_node", script)
        self.assertIn("check_topic_hz /neupan_cmd_vel", script)
        self.assertIn("check_topic_hz /neupan/ackermann_cmd", script)
        self.assertIn("rate >= 10.0", script)

    def test_runtime_check_treats_missing_checkpoint_as_hard_failure(self):
        script = (WORKSPACE_ROOT / "scripts" / "check_neupan_runtime.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("REPLACE_WITH_TRAINED_MKMINI_DUNE_CHECKPOINT", script)
        self.assertIn("Train MK-mini DUNE", script)


if __name__ == "__main__":
    unittest.main()
