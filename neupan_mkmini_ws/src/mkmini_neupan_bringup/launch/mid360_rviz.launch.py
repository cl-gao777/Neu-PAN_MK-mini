import os
import shutil
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _rviz_node(context):
    rviz_config = LaunchConfiguration("rviz_config").perform(context)
    runtime_config = os.path.join(
        tempfile.gettempdir(), "mkmini_mid360_fast_lio.rviz"
    )
    shutil.copyfile(rviz_config, runtime_config)

    return [
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            output="screen",
            arguments=["-d", runtime_config],
        )
    ]


def generate_launch_description():
    share = get_package_share_directory("mkmini_neupan_bringup")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "rviz_config",
                default_value=os.path.join(share, "rviz", "mid360_fast_lio.rviz"),
            ),
            OpaqueFunction(function=_rviz_node),
        ]
    )
