import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def _include(package_name, launch_file, condition=None, launch_arguments=None):
    share = get_package_share_directory(package_name)
    arguments = {
        "launch_description_source": PythonLaunchDescriptionSource(
            os.path.join(share, "launch", launch_file)
        )
    }
    if condition is not None:
        arguments["condition"] = condition
    if launch_arguments is not None:
        arguments["launch_arguments"] = launch_arguments.items()
    return IncludeLaunchDescription(**arguments)


def generate_launch_description():
    start_mid360 = LaunchConfiguration("start_mid360")
    start_visualization_cloud = LaunchConfiguration("start_visualization_cloud")
    start_scan_pipeline = LaunchConfiguration("start_scan_pipeline")
    start_neupan = LaunchConfiguration("start_neupan")
    neupan_config = LaunchConfiguration("neupan_config")
    visualization_cloud_condition = IfCondition(
        PythonExpression([start_visualization_cloud, " or ", start_scan_pipeline])
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("start_mid360", default_value="false"),
            DeclareLaunchArgument("start_visualization_cloud", default_value="false"),
            DeclareLaunchArgument("start_scan_pipeline", default_value="false"),
            DeclareLaunchArgument("start_neupan", default_value="false"),
            DeclareLaunchArgument("neupan_config", default_value=""),
            _include(
                "mkmini_neupan_bringup",
                "mid360_driver.launch.py",
                condition=IfCondition(start_mid360),
            ),
            Node(
                package="mkmini_neupan_bringup",
                executable="custom_msg_to_pointcloud2",
                name="custom_msg_to_pointcloud2",
                condition=visualization_cloud_condition,
                output="screen",
                parameters=[
                    {
                        "input_topic": "/livox/lidar",
                        "output_topic": "/livox/points",
                        "frame_id": "livox_frame",
                    }
                ],
            ),
            _include(
                "mkmini_neupan_bringup",
                "perception_slam.launch.py",
                condition=IfCondition(start_scan_pipeline),
            ),
            _include("mkmini_neupan_bringup", "navigation.launch.py"),
            _include(
                "mkmini_neupan_bringup",
                "neupan.launch.py",
                condition=IfCondition(start_neupan),
                launch_arguments={"neupan_config": neupan_config},
            ),
            _include("mkmini_neupan_bridge", "mkmini_neupan_control.launch.py"),
        ]
    )
