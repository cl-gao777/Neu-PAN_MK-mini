from pathlib import Path
from types import SimpleNamespace
import json
import unittest

from mkmini_neupan_bringup.custom_msg_to_pointcloud2_node import (
    POINT_FIELDS,
    iter_xyzi_points,
    output_frame_id,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class CustomMsgToPointCloud2Test(unittest.TestCase):
    def test_iter_xyzi_points_uses_livox_reflectivity_as_intensity(self):
        custom_msg = SimpleNamespace(
            points=[
                SimpleNamespace(x=1, y=2, z=3, reflectivity=42),
                SimpleNamespace(x=-1.5, y=0.25, z=4.5, reflectivity=7),
            ]
        )

        self.assertEqual(
            list(iter_xyzi_points(custom_msg)),
            [(1.0, 2.0, 3.0, 42.0), (-1.5, 0.25, 4.5, 7.0)],
        )

    def test_output_frame_defaults_to_livox_frame_but_can_preserve_input_header(self):
        custom_msg = SimpleNamespace(header=SimpleNamespace(frame_id="input_frame"))

        self.assertEqual(output_frame_id(custom_msg, "livox_frame"), "livox_frame")
        self.assertEqual(output_frame_id(custom_msg, ""), "input_frame")

    def test_pointcloud2_fields_match_scan_conversion_contract(self):
        self.assertEqual(
            POINT_FIELDS,
            (
                ("x", 0),
                ("y", 4),
                ("z", 8),
                ("intensity", 12),
            ),
        )

    def test_full_stack_launch_starts_custom_msg_converter_before_scan_pipeline(self):
        launch_file = (PACKAGE_ROOT / "launch" / "full_stack.launch.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('DeclareLaunchArgument("start_mid360", default_value="false")', launch_file)
        self.assertIn('"mid360_driver.launch.py"', launch_file)
        self.assertIn("IfCondition(start_mid360)", launch_file)
        self.assertIn('executable="custom_msg_to_pointcloud2"', launch_file)
        self.assertIn('"input_topic": "/livox/lidar"', launch_file)
        self.assertIn('"output_topic": "/livox/points"', launch_file)
        self.assertLess(
            launch_file.index('executable="custom_msg_to_pointcloud2"'),
            launch_file.index('"perception_slam.launch.py"'),
        )

    def test_scan_pipeline_defaults_to_converted_pointcloud2_topic(self):
        launch_file = (
            PACKAGE_ROOT / "launch" / "perception_slam.launch.py"
        ).read_text(encoding="utf-8")

        self.assertIn('DeclareLaunchArgument("cloud_topic", default_value="/livox/points")', launch_file)
        self.assertIn('("cloud_in", cloud_topic)', launch_file)

    def test_bringup_installs_converter_console_script_and_livox_dependencies(self):
        setup_py = (PACKAGE_ROOT / "setup.py").read_text(encoding="utf-8")
        package_xml = (PACKAGE_ROOT / "package.xml").read_text(encoding="utf-8")

        self.assertIn("custom_msg_to_pointcloud2", setup_py)
        self.assertIn("find_packages", setup_py)
        self.assertIn('glob("config/*.json")', setup_py)
        self.assertIn("<exec_depend>livox_ros_driver2</exec_depend>", package_xml)
        self.assertIn("<exec_depend>sensor_msgs_py</exec_depend>", package_xml)

    def test_mid360_config_matches_thor_network_contract(self):
        config = json.loads(
            (PACKAGE_ROOT / "config" / "mid360_livox_config.json").read_text(
                encoding="utf-8"
            )
        )

        host_net_info = config["MID360"]["host_net_info"]
        self.assertEqual(host_net_info["point_data_ip"], "192.168.1.50")
        self.assertEqual(host_net_info["imu_data_ip"], "192.168.1.50")
        self.assertEqual(host_net_info["push_msg_ip"], "192.168.1.50")
        self.assertEqual(host_net_info["point_data_port"], 56301)
        self.assertEqual(host_net_info["imu_data_port"], 56401)
        self.assertEqual(host_net_info["push_msg_port"], 56201)
        self.assertEqual(config["lidar_configs"][0]["ip"], "192.168.1.3")
        self.assertEqual(config["lidar_configs"][0]["pcl_data_type"], 1)
        self.assertEqual(
            config["lidar_configs"][0]["extrinsic_parameter"],
            {"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "x": 0, "y": 0, "z": 0},
        )

    def test_mid360_driver_launch_uses_custom_msg_route(self):
        launch_file = (PACKAGE_ROOT / "launch" / "mid360_driver.launch.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('executable="livox_ros_driver2_node"', launch_file)
        self.assertIn('"xfer_format": 1', launch_file)
        self.assertIn('"multi_topic": 0', launch_file)
        self.assertIn('"data_src": 0', launch_file)
        self.assertIn('DeclareLaunchArgument("frame_id", default_value="livox_frame")', launch_file)
        self.assertIn('DeclareLaunchArgument("publish_freq", default_value="10.0")', launch_file)
        self.assertIn('"user_config_path": config_path', launch_file)

    def test_readme_documents_pytest_and_mid360_launch_commands(self):
        readme = (PACKAGE_ROOT.parents[1] / "README.md").read_text(encoding="utf-8")

        self.assertIn("python3 -m pytest", readme)
        self.assertIn(r".venv\Scripts\python.exe -m pytest", readme)
        self.assertIn("ros2 launch mkmini_neupan_bringup mid360_driver.launch.py", readme)
        self.assertIn("start_mid360:=true", readme)


if __name__ == "__main__":
    unittest.main()
