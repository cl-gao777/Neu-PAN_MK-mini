import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node

from mkmini_neupan_bringup.fast_lio_tf import load_fast_lio_tf


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


def _static_transform(parent, child, transform):
    x, y, z = transform.translation
    qx, qy, qz, qw = transform.quaternion
    return Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        arguments=[
            "--x", str(x), "--y", str(y), "--z", str(z),
            "--qx", str(qx), "--qy", str(qy), "--qz", str(qz), "--qw", str(qw),
            "--frame-id", parent, "--child-frame-id", child,
        ],
        output="screen",
    )


def _fast_lio_tf_nodes(context):
    config_path = LaunchConfiguration("fast_lio_tf_config").perform(context)
    try:
        config = load_fast_lio_tf(config_path, require_calibrated=True)
    except ValueError as error:
        raise RuntimeError(str(error)) from error

    identity = type(config.base_to_livox)(
        translation=(0.0, 0.0, 0.0), quaternion=(0.0, 0.0, 0.0, 1.0)
    )
    return [
        _static_transform(config.odom_frame, config.camera_init_frame, identity),
        _static_transform(config.body_frame, config.base_frame, config.body_to_base),
        _static_transform(config.base_frame, config.lidar_frame, config.base_to_livox),
    ]


def generate_launch_description():
    share = get_package_share_directory("mkmini_neupan_bringup")
    start_mid360 = LaunchConfiguration("start_mid360")
    start_fast_lio = LaunchConfiguration("start_fast_lio")
    start_fast_lio_tf = LaunchConfiguration("start_fast_lio_tf")
    start_visualization_cloud = LaunchConfiguration("start_visualization_cloud")
    start_scan_pipeline = LaunchConfiguration("start_scan_pipeline")
    start_slam = LaunchConfiguration("start_slam")
    start_navigation = LaunchConfiguration("start_navigation")
    start_neupan = LaunchConfiguration("start_neupan")
    start_control_bridge = LaunchConfiguration("start_control_bridge")
    start_can_driver = LaunchConfiguration("start_can_driver")
    use_legacy_adapter = LaunchConfiguration("use_legacy_adapter")
    neupan_config = LaunchConfiguration("neupan_config")
    visualization_cloud_condition = IfCondition(
        PythonExpression([
            "'", start_visualization_cloud, "' == 'true' or '",
            start_scan_pipeline, "' == 'true'",
        ])
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("start_mid360", default_value="false"),
            DeclareLaunchArgument("start_fast_lio", default_value="false"),
            DeclareLaunchArgument("start_fast_lio_tf", default_value="false"),
            DeclareLaunchArgument("start_visualization_cloud", default_value="false"),
            DeclareLaunchArgument("start_scan_pipeline", default_value="false"),
            DeclareLaunchArgument("start_slam", default_value="false"),
            DeclareLaunchArgument("start_navigation", default_value="false"),
            DeclareLaunchArgument("start_neupan", default_value="false"),
            DeclareLaunchArgument("start_control_bridge", default_value="false"),
            DeclareLaunchArgument("start_can_driver", default_value="false"),
            DeclareLaunchArgument("use_legacy_adapter", default_value="false"),
            DeclareLaunchArgument("neupan_config", default_value=""),
            DeclareLaunchArgument(
                "fast_lio_tf_config",
                default_value=os.path.join(share, "config", "fast_lio_tf.yaml"),
            ),
            _include(
                "mkmini_neupan_bringup",
                "fast_lio_mid360.launch.py",
                launch_arguments={
                    "start_mid360": start_mid360,
                    "start_fast_lio": start_fast_lio,
                    "start_visualization_cloud": "false",
                    "start_rviz": "false",
                },
            ),
            OpaqueFunction(
                function=_fast_lio_tf_nodes,
                condition=IfCondition(start_fast_lio_tf),
            ),
            Node(
                package="mkmini_neupan_bringup",
                executable="custom_msg_to_pointcloud2",
                name="custom_msg_to_pointcloud2",
                condition=visualization_cloud_condition,
                output="screen",
                parameters=[{
                    "input_topic": "/livox/lidar",
                    "output_topic": "/livox/points",
                    "frame_id": "livox_frame",
                }],
            ),
            _include(
                "mkmini_neupan_bringup",
                "scan_pipeline.launch.py",
                condition=IfCondition(start_scan_pipeline),
            ),
            _include(
                "mkmini_neupan_bringup",
                "perception_slam.launch.py",
                condition=IfCondition(start_slam),
            ),
            _include(
                "mkmini_neupan_bringup",
                "navigation.launch.py",
                condition=IfCondition(start_navigation),
            ),
            _include(
                "mkmini_neupan_bringup",
                "neupan.launch.py",
                condition=IfCondition(start_neupan),
                launch_arguments={"neupan_config": neupan_config},
            ),
            _include(
                "mkmini_neupan_bridge",
                "mkmini_neupan_control.launch.py",
                condition=IfCondition(start_control_bridge),
                launch_arguments={
                    "start_can_driver": start_can_driver,
                    "use_legacy_adapter": use_legacy_adapter,
                },
            ),
        ]
    )
