# NeuPAN 项目与论文索引

## 必需资料

- [NeuPAN 核心库](https://github.com/hanruihua/NeuPAN)：算法实现、阿克曼仿真、
  自定义几何配置和 DUNE 训练。
- [NeuPAN ROS2](https://github.com/KevinLADLee/neupan_ros2)：支持 Jazzy/Humble 的
  ROS wrapper，作为本项目的集成起点。
- [NeuPAN ROS1](https://github.com/hanruihua/neupan_ros)：仅用于参考原始 ROS 接口
  与可视化设计，不部署到 Jazzy 真机。
- [NeuPAN 论文](https://arxiv.org/abs/2403.06828)：必读理论与实验依据。
- [ir-sim](https://github.com/hanruihua/ir-sim)：在真机测试前快速验证阿克曼配置。

## 传感器、定位与导航

- [livox_ros_driver2](https://github.com/Livox-SDK/livox_ros_driver2)：Mid-360 ROS2
  驱动。进行二维激光投影时需配置 PointCloud2 输出。
- [FAST_LIO ROS2](https://github.com/hku-mars/FAST_LIO/tree/ROS2)：主要里程计来源。
- [SLAM Toolbox](https://github.com/SteveMacenski/slam_toolbox)：在线二维占据地图
  和 `map -> odom`。
- [Navigation2](https://github.com/ros-navigation/navigation2)：任务编排和全局路径生成。

## 后续工作，不进入三周关键路径

- [MfNeuPAN](https://arxiv.org/abs/2511.17013)：面向动态环境的多帧扩展，应在基线系统稳定后研究。
- [librealsense](https://github.com/realsenseai/librealsense)：D455 驱动与后续近场感知/融合工作。
