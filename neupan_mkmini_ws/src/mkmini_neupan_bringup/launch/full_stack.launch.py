import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _include(package_name, launch_file, condition=None):
    share = get_package_share_directory(package_name)
    arguments = {
        "launch_description_source": PythonLaunchDescriptionSource(
            os.path.join(share, "launch", launch_file)
        )
    }
    if condition is not None:
        arguments["condition"] = condition
    return IncludeLaunchDescription(**arguments)


def generate_launch_description():
    start_mid360 = LaunchConfiguration("start_mid360")
    start_neupan = LaunchConfiguration("start_neupan")

    return LaunchDescription(
        [
            DeclareLaunchArgument("start_mid360", default_value="false"),
            DeclareLaunchArgument("start_neupan", default_value="false"),
            _include(
                "mkmini_neupan_bringup",
                "mid360_driver.launch.py",
                condition=IfCondition(start_mid360),
            ),
            Node(
                package="mkmini_neupan_bringup",
                executable="custom_msg_to_pointcloud2",
                name="custom_msg_to_pointcloud2",
                output="screen",
                parameters=[
                    {
                        "input_topic": "/livox/lidar",
                        "output_topic": "/livox/points",
                        "frame_id": "livox_frame",
                    }
                ],
            ),
            _include("mkmini_neupan_bringup", "perception_slam.launch.py"),
            _include("mkmini_neupan_bringup", "navigation.launch.py"),
            _include(
                "mkmini_neupan_bringup",
                "neupan.launch.py",
                condition=IfCondition(start_neupan),
            ),
            _include("mkmini_neupan_bridge", "mkmini_neupan_control.launch.py"),
        ]
    )
