import os

from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from mkmini_neupan_bringup.neupan_config import load_neupan_config_paths


def _checked_neupan_node(context):
    package_name = LaunchConfiguration("neupan_package").perform(context)
    executable = LaunchConfiguration("neupan_executable").perform(context)
    config_path = LaunchConfiguration("neupan_config").perform(context)
    if not config_path:
        share = get_package_share_directory("mkmini_neupan_bringup")
        config_path = os.path.join(
            share, "config", "robots", "mkmini", "robot.yaml"
        )

    try:
        get_package_share_directory(package_name)
    except PackageNotFoundError as error:
        raise RuntimeError(
            "neupan_ros2 is not installed. Import the locked upstreams and rebuild."
        ) from error

    try:
        paths = load_neupan_config_paths(config_path)
    except ValueError as error:
        raise RuntimeError(str(error)) from error

    return [
        Node(
            package=package_name,
            executable=executable,
            name="neupan_node",
            output="screen",
            parameters=[config_path, {"robot_config_dir": str(paths.robot_config_dir)}],
        )
    ]


def generate_launch_description():
    share = get_package_share_directory("mkmini_neupan_bringup")
    default_config = os.path.join(
        share, "config", "robots", "mkmini", "robot.yaml"
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument("neupan_package", default_value="neupan_ros2"),
            DeclareLaunchArgument("neupan_executable", default_value="neupan_node"),
            DeclareLaunchArgument("neupan_config", default_value=default_config),
            OpaqueFunction(function=_checked_neupan_node),
        ]
    )
