import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap


def generate_launch_description():
    share = get_package_share_directory("mkmini_neupan_bringup")
    slam_share = get_package_share_directory("slam_toolbox")
    cloud_topic = LaunchConfiguration("cloud_topic")
    scan_topic = LaunchConfiguration("scan_topic")
    use_sim_time = LaunchConfiguration("use_sim_time")
    scan_params = LaunchConfiguration("scan_params")
    slam_params = LaunchConfiguration("slam_params")

    return LaunchDescription(
        [
            DeclareLaunchArgument("cloud_topic", default_value="/livox/points"),
            DeclareLaunchArgument("scan_topic", default_value="/scan"),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument(
                "scan_params",
                default_value=os.path.join(
                    share, "config", "pointcloud_to_laserscan.yaml"
                ),
            ),
            DeclareLaunchArgument(
                "slam_params",
                default_value=os.path.join(share, "config", "slam_toolbox.yaml"),
            ),
            Node(
                package="pointcloud_to_laserscan",
                executable="pointcloud_to_laserscan_node",
                name="pointcloud_to_laserscan",
                output="screen",
                parameters=[scan_params],
                remappings=[
                    ("cloud_in", cloud_topic),
                    ("scan", scan_topic),
                ],
            ),
            GroupAction(
                [
                    SetRemap(src="/scan", dst=scan_topic),
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(
                                slam_share, "launch", "online_async_launch.py"
                            )
                        ),
                        launch_arguments={
                            "use_sim_time": use_sim_time,
                            "slam_params_file": slam_params,
                        }.items(),
                    ),
                ]
            ),
        ]
    )
