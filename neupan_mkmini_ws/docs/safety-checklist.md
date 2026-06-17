# 真机安全检查表

## 每次测试前

- [ ] 测试遥控接管和物理急停。
- [ ] 指定一名不操作开发电脑的独立安全员。
- [ ] 确认测试区域已与无关人员隔离。
- [ ] 确认 NeuPAN 安全桥限速为 `0.3 m/s`，这也是现场实测最低可响应控制速度；底盘 SDK `/cmd_vel` 适配器默认上限为 `0.8 m/s`，但 NeuPAN 控制期间不得绕过安全桥。
- [ ] 确认倒车功能已禁用。
- [ ] 确认 `/ctrl_cmd` 只有一个发布者。
- [ ] 确认厂商 `cmd_vel_to_ctrl_cmd_node` 未运行。
- [ ] 确认 `/veh_diag_fb` 持续更新，安全桥使用该话题判断整车诊断新鲜度。
- [ ] 确认 `/livox/lidar` 约 `10 Hz` 更新，且类型为 `livox_ros_driver2/msg/CustomMsg`。
- [ ] 确认 `/livox/points` 只有一个有效发布者；需要 `/scan` 时由 `start_scan_pipeline:=true` 管理。
- [ ] 确认 `/scan` 和 `/plan` 在启动 NeuPAN 前均已稳定发布。
- [ ] 架空轮状态下通过反馈确认 `D=4`、`R=2`。
- [ ] 确认 TF 中只有一个 `odom -> base_link` 发布者。
- [ ] 进入 CAN 命令模式前，确认安全桥仍处于未解锁状态。

## 架空轮准入检查

1. 将所有驱动轮可靠架离地面。
2. 仅启动 CAN 驱动和安全桥。
   此阶段使用 `safety_bridge_bench.yaml`，且车辆必须保持架空。
3. 确认未解锁时输出速度为零。
4. 解锁安全桥，并发送持续时间小于一秒的 `0.3 m/s` 命令。
5. 确认前进档反馈为 `4`。
6. 停止发布命令，确认车辆在 `0.3 s` 内收到零速度命令。
7. 分别触发软件急停、物理急停和遥控接管。
8. 所有停车路径全部通过后，才能进行落地测试。
9. 落地测试前切回正式 `safety_bridge.yaml`，确认 TF 定位门控生效。

## 落地测试限制

- 初始速度使用 `0.3 m/s`；静态障碍测试连续成功十次后，才允许在不超过 `0.8 m/s` 的范围内逐步提高。
- 始终保留至少 2 m 的无障碍停车空间。
- 在引入真人横穿前，先使用柔软替代障碍物测试。
- 在超时停车功能得到可靠验证前，禁止进行动态横穿测试。

## NeuPAN 启动前附加检查

- [ ] `neupan_ros2`、`FAST_LIO`、`livox_ros_driver2` 和 `third_party/NeuPAN` 已通过 `scripts/import_upstreams.sh` 导入并构建。
- [ ] 若从宿主机一键启动，先运行 `bash docker/start_real_robot_neupan.sh --dry-run`，确认 workspace、镜像、CAN、LiDAR 和传入 launch 参数符合现场配置。
- [ ] 真机一键启动命令为 `bash docker/start_real_robot_neupan.sh`；如果已经在容器内，可直接运行 `bash scripts/start_real_robot_neupan.sh --dry-run` 或 `bash scripts/start_real_robot_neupan.sh`。该脚本不会自动解锁安全桥，也不会自动发布运动命令。
- [ ] 已运行 `ros2 run mkmini_neupan_bringup thor_neupan_preflight`，且最终输出 `RESULT  PASS`。
- [ ] preflight 使用的 `start_scan_pipeline:=true`、`start_mid360:=true/false`、`neupan_config:=...` 等参数与正式 `full_stack.launch.py start_neupan:=true` 启动命令一致。
- [ ] `/scan` 达到预期频率，且来自当前唯一的 `/livox/points` 转换链路。
- [ ] `/plan` 由 Nav2 planner 正常发布；若现场 Nav2 只有收到目标后才发布 `/plan`，需先给出测试目标再运行 preflight。
- [ ] `/veh_diag_fb` 持续更新，且诊断状态无故障、急停和 EPS 故障。
- [ ] `neupan_mkmini.yaml` 已替换为训练好的 MK-mini DUNE checkpoint。
- [ ] `full_stack.launch.py start_neupan:=true` 只在上述条件满足后使用。

## NeuPAN 启动后验收

- [ ] `/neupan_cmd_vel` 与 `/neupan/ackermann_cmd` 均达到 10 Hz 以上。
- [ ] `/ctrl_cmd` 仍只有安全桥一个发布者。
- [ ] 厂商 `cmd_vel_to_ctrl_cmd_node` 仍未运行。
