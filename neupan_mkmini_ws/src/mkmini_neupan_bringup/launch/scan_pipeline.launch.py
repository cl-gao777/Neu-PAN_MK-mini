import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory("mkmini_neupan_bringup")
    cloud_topic = LaunchConfiguration("cloud_topic")
    scan_topic = LaunchConfiguration("scan_topic")
    scan_params = LaunchConfiguration("scan_params")

    return LaunchDescription(
        [
            DeclareLaunchArgument("cloud_topic", default_value="/livox/points"),
            DeclareLaunchArgument("scan_topic", default_value="/scan"),
            DeclareLaunchArgument(
                "scan_params",
                default_value=os.path.join(
                    share, "config", "pointcloud_to_laserscan.yaml"
                ),
            ),
            Node(
                package="pointcloud_to_laserscan",
                executable="pointcloud_to_laserscan_node",
                name="pointcloud_to_laserscan",
                output="screen",
                parameters=[scan_params],
                remappings=[("cloud_in", cloud_topic), ("scan", scan_topic)],
            ),
        ]
    )
