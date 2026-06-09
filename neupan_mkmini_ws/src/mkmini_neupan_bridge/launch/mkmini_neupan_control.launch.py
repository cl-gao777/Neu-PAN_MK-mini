import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory("mkmini_neupan_bridge")
    bridge_params = LaunchConfiguration("bridge_params")
    can_params = LaunchConfiguration("can_params")
    start_can_driver = LaunchConfiguration("start_can_driver")
    use_legacy_adapter = LaunchConfiguration("use_legacy_adapter")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "bridge_params",
                default_value=os.path.join(share, "config", "safety_bridge.yaml"),
            ),
            DeclareLaunchArgument(
                "can_params",
                default_value=os.path.join(share, "config", "yhs_can_control_safe.yaml"),
            ),
            DeclareLaunchArgument("start_can_driver", default_value="true"),
            DeclareLaunchArgument("use_legacy_adapter", default_value="true"),
            Node(
                package="yhs_can_control",
                executable="yhs_can_control_node",
                name="yhs_can_control_node",
                output="screen",
                parameters=[can_params],
                condition=IfCondition(start_can_driver),
            ),
            Node(
                package="mkmini_neupan_bridge",
                executable="legacy_neupan_twist_adapter",
                name="legacy_neupan_twist_adapter",
                output="screen",
                parameters=[bridge_params],
                condition=IfCondition(use_legacy_adapter),
            ),
            Node(
                package="mkmini_neupan_bridge",
                executable="ackermann_safety_bridge",
                name="ackermann_safety_bridge",
                output="screen",
                parameters=[bridge_params],
            ),
        ]
    )
