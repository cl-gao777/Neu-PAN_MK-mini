from pathlib import Path
import unittest

from mkmini_neupan_bringup.neupan_config import (
    load_neupan_config_paths,
    parse_robot_parameters,
    resolve_config_path,
)


ROBOT_CONFIG = """
neupan_node:
  ros__parameters:
    planner_config_file: planner.yaml
    dune_checkpoint_file: /workspaces/MK-mini_ws/neupan_mkmini_ws/checkpoints/dune/model_5000.pth
    map_frame: map
"""


class NeuPANConfigTest(unittest.TestCase):
    def test_extracts_official_ros_parameters(self):
        parameters = parse_robot_parameters(ROBOT_CONFIG)

        self.assertEqual(parameters["planner_config_file"], "planner.yaml")
        self.assertEqual(
            parameters["dune_checkpoint_file"],
            "/workspaces/MK-mini_ws/neupan_mkmini_ws/checkpoints/dune/model_5000.pth",
        )

    def test_resolves_relative_paths_against_robot_config_directory(self):
        robot_dir = Path("/opt/robot/config/robots/mkmini")

        self.assertEqual(
            resolve_config_path("planner.yaml", robot_dir),
            robot_dir / "planner.yaml",
        )
        self.assertEqual(
            resolve_config_path("/models/dune.pth", robot_dir),
            Path("/models/dune.pth"),
        )

    def test_loads_and_validates_robot_planner_and_checkpoint_paths(self):
        robot_dir = Path(__file__).parent / "fixtures"
        robot_config = robot_dir / "robot.yaml"

        paths = load_neupan_config_paths(robot_config)

        self.assertEqual(paths.robot_config, robot_config)
        self.assertEqual(paths.robot_config_dir, robot_dir)
        self.assertEqual(paths.planner_config, robot_dir / "planner.yaml")
        self.assertEqual(paths.dune_checkpoint, robot_dir / "model.pth")

    def test_missing_official_parameter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "planner_config_file"):
            parse_robot_parameters(
                "neupan_node:\n  ros__parameters:\n    dune_checkpoint_file: model.pth\n"
            )


if __name__ == "__main__":
    unittest.main()
