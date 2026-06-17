import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
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
    share = get_package_share_directory("mkmini_neupan_bringup")

    start_mid360 = LaunchConfiguration("start_mid360")
    start_fast_lio = LaunchConfiguration("start_fast_lio")
    start_visualization_cloud = LaunchConfiguration("start_visualization_cloud")
    start_rviz = LaunchConfiguration("start_rviz")
    livox_config_path = LaunchConfiguration("livox_config_path")
    fast_lio_config_path = LaunchConfiguration("fast_lio_config_path")
    fast_lio_config_file = LaunchConfiguration("fast_lio_config_file")
    rviz_config = LaunchConfiguration("rviz_config")

    return LaunchDescription(
        [
            DeclareLaunchArgument("start_mid360", default_value="true"),
            DeclareLaunchArgument("start_fast_lio", default_value="true"),
            DeclareLaunchArgument("start_visualization_cloud", default_value="true"),
            DeclareLaunchArgument("start_rviz", default_value="false"),
            DeclareLaunchArgument(
                "livox_config_path",
                default_value=os.path.join(share, "config", "mid360_livox_config.json"),
            ),
            DeclareLaunchArgument(
                "fast_lio_config_path",
                default_value=os.path.join(share, "config"),
            ),
            DeclareLaunchArgument(
                "fast_lio_config_file",
                default_value="fast_lio_mid360.yaml",
            ),
            DeclareLaunchArgument(
                "rviz_config",
                default_value=os.path.join(share, "rviz", "mid360_fast_lio.rviz"),
            ),
            _include(
                "mkmini_neupan_bringup",
                "mid360_driver.launch.py",
                condition=IfCondition(start_mid360),
                launch_arguments={"config_path": livox_config_path},
            ),
            _include(
                "fast_lio",
                "mapping.launch.py",
                condition=IfCondition(start_fast_lio),
                launch_arguments={
                    "config_path": fast_lio_config_path,
                    "config_file": fast_lio_config_file,
                    "rviz": "false",
                },
            ),
            Node(
                package="mkmini_neupan_bringup",
                executable="custom_msg_to_pointcloud2",
                name="custom_msg_to_pointcloud2",
                condition=IfCondition(start_visualization_cloud),
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
                "mid360_rviz.launch.py",
                condition=IfCondition(start_rviz),
                launch_arguments={"rviz_config": rviz_config},
            ),
        ]
    )
