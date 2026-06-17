import os
from pathlib import Path

from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


CHECKPOINT_PLACEHOLDER = "REPLACE_WITH_TRAINED_MKMINI_DUNE_CHECKPOINT"


def _extract_dune_checkpoint(config_text):
    in_pan_block = False
    pan_indent = 0
    for line in config_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if stripped == "pan:":
            in_pan_block = True
            pan_indent = indent
            continue
        if in_pan_block and indent <= pan_indent:
            in_pan_block = False
        if in_pan_block and stripped.startswith("dune_checkpoint:"):
            value = stripped.split(":", 1)[1].strip()
            return value.strip("\"'")
    return None


def _checked_neupan_node(context):
    package_name = LaunchConfiguration("neupan_package").perform(context)
    executable = LaunchConfiguration("neupan_executable").perform(context)
    config_path = LaunchConfiguration("neupan_config").perform(context)
    scan_topic = LaunchConfiguration("scan_topic").perform(context)
    plan_topic = LaunchConfiguration("plan_topic").perform(context)
    output_topic = LaunchConfiguration("output_topic").perform(context)
    if not config_path:
        share = get_package_share_directory("mkmini_neupan_bringup")
        config_path = os.path.join(share, "config", "neupan_mkmini.yaml")

    try:
        get_package_share_directory(package_name)
    except PackageNotFoundError as error:
        raise RuntimeError(
            "neupan_ros2 is not installed in this workspace. Import "
            "mkmini_neupan.repos and rebuild before launching NeuPAN."
        ) from error

    if not os.path.isfile(config_path):
        raise RuntimeError(f"NeuPAN MK-mini config does not exist: {config_path}")

    with open(config_path, encoding="utf-8") as config_file:
        config = config_file.read()
    if CHECKPOINT_PLACEHOLDER in config:
        raise RuntimeError(
            "Train MK-mini DUNE before launching NeuPAN on the robot. "
            "Replace REPLACE_WITH_TRAINED_MKMINI_DUNE_CHECKPOINT in "
            f"{config_path} with the trained checkpoint path."
        )
    checkpoint = _extract_dune_checkpoint(config)
    if not checkpoint:
        raise RuntimeError(
            f"pan.dune_checkpoint is missing from NeuPAN config: {config_path}"
        )
    checkpoint_path = Path(checkpoint).expanduser()
    if not checkpoint_path.is_file():
        raise RuntimeError(
            "NeuPAN MK-mini DUNE checkpoint does not exist: "
            f"{checkpoint_path}. Update pan.dune_checkpoint in {config_path}."
        )

    return [
        Node(
            package=package_name,
            executable=executable,
            name="neupan_node",
            output="screen",
            parameters=[
                {"config_file": config_path},
                {"config_path": config_path},
                {"planner_config": config_path},
            ],
            remappings=[
                ("/scan", scan_topic),
                ("scan", scan_topic),
                ("/plan", plan_topic),
                ("plan", plan_topic),
                ("/neupan_cmd_vel", output_topic),
                ("neupan_cmd_vel", output_topic),
            ],
        )
    ]


def generate_launch_description():
    share = get_package_share_directory("mkmini_neupan_bringup")
    default_config = os.path.join(share, "config", "neupan_mkmini.yaml")

    return LaunchDescription(
        [
            DeclareLaunchArgument("neupan_package", default_value="neupan_ros2"),
            DeclareLaunchArgument("neupan_executable", default_value="neupan_node"),
            DeclareLaunchArgument("neupan_config", default_value=default_config),
            DeclareLaunchArgument("scan_topic", default_value="/scan"),
            DeclareLaunchArgument("plan_topic", default_value="/plan"),
            DeclareLaunchArgument("output_topic", default_value="/neupan_cmd_vel"),
            OpaqueFunction(function=_checked_neupan_node),
        ]
    )
