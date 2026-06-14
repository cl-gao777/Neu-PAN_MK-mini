# Neu-PAN MK-mini

本仓库是面向宇合森 MK-mini 底盘的父级工作区，包含底盘 ROS 2 SDK 和 NeuPAN 集成工作区两部分。仓库根目录只负责组织两个子项目；不要在根目录直接执行 `colcon build`。

## 目录结构

```text
.
├── ROS2_MK-mini/
│   ├── docs/
│   ├── src/yhs_can_control/
│   └── src/yhs_can_interfaces/
├── neupan_mkmini_ws/
│   ├── docs/
│   ├── scripts/
│   └── src/
├── LICENSE
├── README.md
└── .gitignore
```

## 子项目

| 路径 | 作用 |
| --- | --- |
| [`ROS2_MK-mini/`](ROS2_MK-mini/) | MK-mini 底盘 ROS 2 SDK，包含厂商消息接口、SocketCAN 底盘控制、里程计、TF 和实车测试文档。 |
| [`neupan_mkmini_ws/`](neupan_mkmini_ws/) | NeuPAN 到 MK-mini 的集成工作区，包含 Ackermann 安全桥、bringup、SLAM/Nav2 配置、检查脚本和验收文档。 |

详细使用方式请先阅读两个子目录自己的 README：

- [`ROS2_MK-mini/README.md`](ROS2_MK-mini/README.md)
- [`neupan_mkmini_ws/README.md`](neupan_mkmini_ws/README.md)

## 推荐使用顺序

1. 先进入 `ROS2_MK-mini/`，验证 MK-mini 底盘 SDK 能够构建、连接 CAN 总线并发布 `/ctrl_cmd`、`/chassis_info_fb`、`/veh_diag_fb`、`/odom` 等底盘接口。
2. 再进入 `neupan_mkmini_ws/`，按 `mkmini_neupan.repos` 导入上游依赖，并把 `ROS2_MK-mini/src/yhs_can_control` 与 `ROS2_MK-mini/src/yhs_can_interfaces` 复制到该工作区的 `src/`。
3. 在 `neupan_mkmini_ws/` 内运行安全桥、SLAM/Nav2 和 NeuPAN 集成相关构建与测试。

示例：

```bash
cd ~/ROS2_MK-mini
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install

cd ~/neupan_mkmini_ws
vcs import . < mkmini_neupan.repos
cp -a ~/ROS2_MK-mini/src/yhs_can_control src/
cp -a ~/ROS2_MK-mini/src/yhs_can_interfaces src/
colcon build --symlink-install \
  --packages-select yhs_can_interfaces yhs_can_control \
  mkmini_neupan_bridge mkmini_neupan_bringup
```

## 注意事项

- 根目录不是 ROS 2 工作区入口；分别在 `ROS2_MK-mini/` 和 `neupan_mkmini_ws/` 中构建。
- `build/`、`install/`、`log/`、`.venv/`、`.api_tmp/` 和本地 Git 备份目录不会进入版本库。
- 实车测试前必须保留遥控器、物理急停和独立安全员，并先完成子项目文档中的安全检查。
