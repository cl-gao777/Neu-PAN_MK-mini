import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def _include(package_name, launch_file):
    share = get_package_share_directory(package_name)
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(share, "launch", launch_file))
    )


def generate_launch_description():
    return LaunchDescription(
        [
            _include("mkmini_neupan_bringup", "perception_slam.launch.py"),
            _include("mkmini_neupan_bringup", "navigation.launch.py"),
            _include("mkmini_neupan_bridge", "mkmini_neupan_control.launch.py"),
        ]
    )
