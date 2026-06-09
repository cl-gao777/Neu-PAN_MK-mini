from pathlib import Path
import unittest


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


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


if __name__ == "__main__":
    unittest.main()
