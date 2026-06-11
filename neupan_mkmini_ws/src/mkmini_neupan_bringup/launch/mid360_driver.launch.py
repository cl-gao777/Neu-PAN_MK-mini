import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory("mkmini_neupan_bringup")
    config_path = LaunchConfiguration("config_path")
    frame_id = LaunchConfiguration("frame_id")
    publish_freq = LaunchConfiguration("publish_freq")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "config_path",
                default_value=os.path.join(
                    share, "config", "mid360_livox_config.json"
                ),
            ),
            DeclareLaunchArgument("frame_id", default_value="livox_frame"),
            DeclareLaunchArgument("publish_freq", default_value="10.0"),
            Node(
                package="livox_ros_driver2",
                executable="livox_ros_driver2_node",
                name="livox_lidar_publisher",
                output="screen",
                parameters=[
                    {
                        "xfer_format": 1,
                        "multi_topic": 0,
                        "data_src": 0,
                        "publish_freq": publish_freq,
                        "output_type": 0,
                        "frame_id": frame_id,
                        "user_config_path": config_path,
                    }
                ],
            ),
        ]
    )
