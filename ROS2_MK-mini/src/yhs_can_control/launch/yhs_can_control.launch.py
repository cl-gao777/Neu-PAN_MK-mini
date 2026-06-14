#!/usr/bin/env python3

# 启动 MK-mini 底盘驱动的默认 launch：
# 1. yhs_can_control_node 负责 CAN 桥接和反馈发布；
# 2. cmd_vel_to_ctrl_cmd_node 负责把 Nav2 的 /cmd_vel 转为 /ctrl_cmd。

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share_dir = get_package_share_directory('yhs_can_control')
    parameter_file = LaunchConfiguration('params_file')

    params_declare = DeclareLaunchArgument(
        'params_file',
        default_value=os.path.join(share_dir, 'params', 'cfg.yaml'),
        description='ROS 2 参数文件路径。',
    )

    yhs_can_control_node = Node(
        package='yhs_can_control',
        executable='yhs_can_control_node',
        name='yhs_can_control_node',
        output='screen',
        parameters=[parameter_file],
    )

    cmd_vel_adapter_node = Node(
        package='yhs_can_control',
        executable='cmd_vel_to_ctrl_cmd_node',
        name='cmd_vel_to_ctrl_cmd_node',
        output='screen',
        parameters=[parameter_file],
    )

    return LaunchDescription([
        params_declare,
        yhs_can_control_node,
        cmd_vel_adapter_node,
    ])
