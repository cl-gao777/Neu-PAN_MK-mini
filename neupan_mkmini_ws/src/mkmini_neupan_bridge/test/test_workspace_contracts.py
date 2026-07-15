from pathlib import Path
import unittest


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
MONOREPO_ROOT = WORKSPACE_ROOT.parent


class WorkspaceContractTest(unittest.TestCase):
    def test_stack_check_frequency_probe_has_a_timeout(self):
        script = (WORKSPACE_ROOT / "scripts" / "check_stack.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("timeout 6s ros2 topic hz", script)

    def test_scan_topic_launch_argument_is_remapped_into_slam_toolbox(self):
        launch_file = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "launch"
            / "perception_slam.launch.py"
        ).read_text(encoding="utf-8")

        self.assertIn('SetRemap(src="/scan", dst=scan_topic)', launch_file)

    def test_formal_and_bench_configs_use_expected_localization_gates(self):
        config_dir = (
            WORKSPACE_ROOT / "src" / "mkmini_neupan_bridge" / "config"
        )
        formal = (config_dir / "safety_bridge.yaml").read_text(encoding="utf-8")
        bench = (config_dir / "safety_bridge_bench.yaml").read_text(encoding="utf-8")

        self.assertIn("require_localization: true", formal)
        self.assertIn("require_localization: false", bench)
        for config in (formal, bench):
            with self.subTest(config=config[:40]):
                self.assertIn("min_drive_speed_mps: 0.5", config)
                self.assertIn("max_speed_mps: 0.6", config)
                self.assertIn("allow_reverse: false", config)

    def test_safety_bridge_uses_dedicated_diagnostic_topic(self):
        config_dir = (
            WORKSPACE_ROOT / "src" / "mkmini_neupan_bridge" / "config"
        )
        formal = (config_dir / "safety_bridge.yaml").read_text(encoding="utf-8")
        bench = (config_dir / "safety_bridge_bench.yaml").read_text(encoding="utf-8")
        bridge_node = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bridge"
            / "mkmini_neupan_bridge"
            / "ackermann_safety_bridge_node.py"
        ).read_text(encoding="utf-8")
        can_node = (
            MONOREPO_ROOT
            / "ROS2_MK-mini"
            / "src"
            / "yhs_can_control"
            / "src"
            / "yhs_can_control_node.cpp"
        ).read_text(encoding="utf-8")

        for config in (formal, bench):
            with self.subTest(config=config[:40]):
                self.assertIn("diagnostic_topic: /veh_diag_fb", config)
                self.assertNotIn("feedback_topic:", config)
        self.assertIn("VehDiagFb", bridge_node)
        self.assertIn('"diagnostic_topic", "/veh_diag_fb"', bridge_node)
        self.assertIn("create_publisher<yhs_can_interfaces::msg::VehDiagFb>", can_node)
        self.assertIn("veh_diag_fb_publisher_->publish(msg)", can_node)

    def test_safety_bridge_gates_every_safety_critical_diagnostic_field(self):
        bridge_node = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bridge"
            / "mkmini_neupan_bridge"
            / "ackermann_safety_bridge_node.py"
        ).read_text(encoding="utf-8")

        for field in [
            "veh_fb_fault_level",
            "veh_fb_auto_can_ctrl_cmd",
            "veh_fb_eps_dis_on_line",
            "veh_fb_eps_fault",
            "veh_fb_eps_mosf_et_ot",
            "veh_fb_eps_warning",
            "veh_fb_eps_dis_work",
            "veh_fb_eps_over_current",
            "veh_fb_ehb_ecu_fault",
            "veh_fb_ehb_dis_on_line",
            "veh_fb_ehb_work_model_fault",
            "veh_fb_ehb_dis_en",
            "veh_fb_ehb_anguler_fault",
            "veh_fb_ehb_ot",
            "veh_fb_ehb_power_fault",
            "veh_fb_ehb_sensor_abnomal",
            "veh_fb_ehb_motor_fault",
            "veh_fb_ehb_oil_press_sensor_fault",
            "veh_fb_ehb_oil_fault",
            "veh_fb_ld_rv_mcu_fault",
            "veh_fb_rd_rv_mcu_fault",
            "veh_fb_aux_bms_dis_on_line",
            "veh_fb_aux_scram",
            "veh_fb_aux_remote_close",
            "veh_fb_aux_remote_dis_on_line",
        ]:
            with self.subTest(field=field):
                self.assertIn(f"diagnostic.{field}", bridge_node)

    def test_all_mkmini_control_configs_use_official_drive_gear(self):
        bridge_config = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bridge"
            / "config"
            / "safety_bridge.yaml"
        ).read_text(encoding="utf-8")
        bench_config = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bridge"
            / "config"
            / "safety_bridge_bench.yaml"
        ).read_text(encoding="utf-8")
        vendor_config = (
            MONOREPO_ROOT
            / "ROS2_MK-mini"
            / "src"
            / "yhs_can_control"
            / "params"
            / "cfg.yaml"
        ).read_text(encoding="utf-8")

        for config in (bridge_config, bench_config, vendor_config):
            with self.subTest(config=config[:40]):
                self.assertIn("forward_gear: 4", config)
                self.assertIn("reverse_gear: 2", config)

    def test_vendor_control_path_has_independent_0_6_mps_watchdog_gate(self):
        vendor_config = (
            MONOREPO_ROOT
            / "ROS2_MK-mini"
            / "src"
            / "yhs_can_control"
            / "params"
            / "cfg.yaml"
        ).read_text(encoding="utf-8")
        deployment_config = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bridge"
            / "config"
            / "yhs_can_control_safe.yaml"
        ).read_text(encoding="utf-8")
        can_node = (
            MONOREPO_ROOT
            / "ROS2_MK-mini"
            / "src"
            / "yhs_can_control"
            / "src"
            / "yhs_can_control_node.cpp"
        ).read_text(encoding="utf-8")
        adapter = (
            MONOREPO_ROOT
            / "ROS2_MK-mini"
            / "src"
            / "yhs_can_control"
            / "src"
            / "cmd_vel_to_ctrl_cmd_node.cpp"
        ).read_text(encoding="utf-8")

        for config in (vendor_config, deployment_config):
            with self.subTest(config=config[:40]):
                self.assertIn("max_velocity_mps: 0.6", config)
                self.assertIn("max_steering_deg: 25.0", config)
                self.assertIn("command_timeout_sec: 0.3", config)
                self.assertIn("send_rate_hz: 50.0", config)
                self.assertIn("allow_reverse: false", config)
                self.assertIn("forward_gear: 4", config)
                self.assertIn("reverse_gear: 2", config)

        self.assertIn("ControlCommandGate", can_node)
        self.assertIn("control_command_gate_.update", can_node)
        self.assertIn("create_wall_timer", can_node)
        self.assertIn("steady_clock", can_node)
        self.assertIn("max_velocity_mps", adapter)
        self.assertIn('"max_velocity_mps", 0.6', adapter)

    def test_ctrl_cmd_message_documents_official_gear_enum(self):
        message = (
            MONOREPO_ROOT
            / "ROS2_MK-mini"
            / "src"
            / "yhs_can_interfaces"
            / "msg"
            / "CtrlCmd.msg"
        ).read_text(encoding="utf-8")

        for expected in [
            "00 disable",
            "01 P",
            "02 R",
            "03 N",
            "04 D",
        ]:
            self.assertIn(expected, message)

    def test_ctrl_cmd_publisher_does_not_access_a_nonexistent_header(self):
        bridge_node = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bridge"
            / "mkmini_neupan_bridge"
            / "ackermann_safety_bridge_node.py"
        ).read_text(encoding="utf-8")
        message = (
            MONOREPO_ROOT
            / "ROS2_MK-mini"
            / "src"
            / "yhs_can_interfaces"
            / "msg"
            / "CtrlCmd.msg"
        ).read_text(encoding="utf-8")

        self.assertNotIn("std_msgs/Header", message)
        self.assertNotIn("output.header", bridge_node)

    def test_full_stack_has_opt_in_neupan_launch(self):
        launch_file = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "launch"
            / "full_stack.launch.py"
        ).read_text(encoding="utf-8")

        self.assertIn('DeclareLaunchArgument("start_neupan", default_value="false")', launch_file)
        self.assertIn('DeclareLaunchArgument("start_slam", default_value="false")', launch_file)
        self.assertIn('DeclareLaunchArgument("start_navigation", default_value="false")', launch_file)
        self.assertIn('"neupan.launch.py"', launch_file)
        self.assertIn("IfCondition(start_neupan)", launch_file)
        self.assertIn("IfCondition(start_navigation)", launch_file)

    def test_full_stack_control_path_is_opt_in(self):
        bringup = WORKSPACE_ROOT / "src" / "mkmini_neupan_bringup"
        bridge = WORKSPACE_ROOT / "src" / "mkmini_neupan_bridge"

        full_stack = (bringup / "launch" / "full_stack.launch.py").read_text(
            encoding="utf-8"
        )
        control_launch = (
            bridge / "launch" / "mkmini_neupan_control.launch.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'DeclareLaunchArgument("start_control_bridge", default_value="false")',
            full_stack,
        )
        self.assertIn(
            'DeclareLaunchArgument("start_can_driver", default_value="false")',
            full_stack,
        )
        self.assertIn(
            'DeclareLaunchArgument("use_legacy_adapter", default_value="false")',
            full_stack,
        )
        self.assertIn("IfCondition(start_control_bridge)", full_stack)
        self.assertIn('"start_can_driver": start_can_driver', full_stack)
        self.assertIn('"use_legacy_adapter": use_legacy_adapter', full_stack)

        self.assertIn(
            'DeclareLaunchArgument("start_can_driver", default_value="false")',
            control_launch,
        )
        self.assertIn(
            'DeclareLaunchArgument("use_legacy_adapter", default_value="false")',
            control_launch,
        )

    def test_official_neupan_config_and_launch_contract(self):
        package = WORKSPACE_ROOT / "src" / "mkmini_neupan_bringup"
        robot = (package / "config" / "robots" / "mkmini" / "robot.yaml").read_text(encoding="utf-8")
        planner = (package / "config" / "robots" / "mkmini" / "planner.yaml").read_text(encoding="utf-8")
        launch_file = (package / "launch" / "neupan.launch.py").read_text(encoding="utf-8")
        setup_py = (package / "setup.py").read_text(encoding="utf-8")

        for value in ["planner_config_file", "dune_checkpoint_file", "robot_type", "robot_description"]:
            self.assertIn(value, robot)
        self.assertIn('robot_description: "YUHESEN MK-mini Ackermann robot"', robot)
        self.assertIn("plan_input_topic: /plan", robot)
        for value in [
            "enable_visualization: false",
            "enable_dune_markers: false",
            "enable_nrmp_markers: false",
            "enable_robot_marker: false",
        ]:
            self.assertIn(value, robot)
        for obsolete in ["\n    plan_topic:", "\n    visualization:", "\n    show_animation:"]:
            self.assertNotIn(obsolete, robot)
        self.assertIn("ref_speed: 0.55", planner)
        self.assertIn("max_speed: [0.6, 0.4363323129985824]", planner)
        self.assertIn("dune_checkpoint: None", planner)
        self.assertIn("robot_config_dir", launch_file)
        self.assertIn("parameters=[config_path, {\"robot_config_dir\":", launch_file)
        for obsolete in ['\"config_file\"', '\"config_path\"', '\"planner_config\"']:
            self.assertNotIn(obsolete, launch_file)
        self.assertIn("os.walk", setup_py)

    def test_fast_lio_full_stack_defaults_and_tf_fail_safe(self):
        package = WORKSPACE_ROOT / "src" / "mkmini_neupan_bringup"
        full_stack = (package / "launch" / "full_stack.launch.py").read_text(encoding="utf-8")
        runner = (WORKSPACE_ROOT / "scripts" / "start_real_robot_neupan.sh").read_text(encoding="utf-8")
        tf_config = (package / "config" / "fast_lio_tf.yaml").read_text(encoding="utf-8")
        nav2 = (package / "config" / "nav2_params.yaml").read_text(encoding="utf-8")
        preflight = (package / "mkmini_neupan_bringup" / "thor_neupan_preflight_node.py").read_text(encoding="utf-8")

        self.assertIn("fast_lio_mid360.launch.py", full_stack)
        self.assertIn("start_fast_lio_tf", full_stack)
        self.assertIn("calibrated: false", tf_config)
        self.assertIn("odom -> camera_init -> body -> base_link -> livox_frame", tf_config)
        for argument in ["start_mid360:=true", "start_fast_lio:=true", "start_scan_pipeline:=true", "start_fast_lio_tf:=true"]:
            self.assertIn(argument, runner)
        self.assertIn("odom_topic: /Odometry", nav2)
        self.assertIn('TopicRateCheck("/Odometry"', preflight)

    def test_all_upstreams_are_pinned_and_lock_file_exists(self):
        expected = {
            "4ffb7ec2dc45ff7ee9024f64083813237906af98",
            "f5ae6d848b54aeae0340af1eb49e3a809dea00a5",
            "13eb05e4e6dd7a765b934d0c5fd6236676a57b49",
            "a4743b095409588842a5b30ddfa27e29d2f99164",
            "c2d6caf23f5a4c7374db6f54e1f3691a5d49940f",
            "80ab6ee74496f8599f184804e8a4a55c499d8c23",
        }
        repos = (WORKSPACE_ROOT / "mkmini_neupan.repos").read_text(encoding="utf-8")
        lock = (WORKSPACE_ROOT / "mkmini_neupan.lock.repos").read_text(encoding="utf-8")
        import_script = (WORKSPACE_ROOT / "scripts" / "import_upstreams.sh").read_text(encoding="utf-8")

        for revision in expected:
            self.assertIn(revision, repos)
            self.assertIn(revision, lock)
        self.assertIn("third_party/yhs_robot_description:", repos)
        self.assertIn("third_party/yhs_robot_description:", lock)
        self.assertNotIn("  src/yhs_robot_description:", repos)
        self.assertIn("mv src/yhs_robot_description third_party/yhs_robot_description", import_script)
        self.assertIn("mkmini_neupan.lock.repos", import_script)

    def test_thor_python_requirements_are_pinned_without_pytorch(self):
        requirements = (WORKSPACE_ROOT / "requirements-thor.txt").read_text(encoding="utf-8")
        bootstrap = (WORKSPACE_ROOT / "scripts" / "bootstrap_jazzy.sh").read_text(encoding="utf-8")
        runtime_lock_example = WORKSPACE_ROOT / "thor-runtime.lock.example.json"

        for dependency in [
            "numpy==1.26.4",
            "scipy==1.13.0",
            "cvxpy==",
            "cvxpylayers==",
            "ecos==",
            "PyYAML==",
            "gctl==1.2",
            "rich==13.9.4",
            "dill==0.3.9",
            "colorama==0.4.6",
        ]:
            self.assertIn(dependency, requirements)
        self.assertNotIn("torch==", requirements.lower())
        self.assertNotIn("pytorch==", requirements.lower())
        self.assertIn("requirements-thor.txt", bootstrap)
        self.assertIn("--no-deps", bootstrap)
        self.assertIn(
            "set +u\nsource /opt/ros/jazzy/setup.bash\nset -u",
            bootstrap,
        )
        self.assertTrue(runtime_lock_example.is_file())
        self.assertIn("--torch-lock-only", bootstrap)
        self.assertNotIn("--runtime-manifest thor-runtime.lock.json", bootstrap)

    def test_thor_docker_image_owns_pytorch_cuda_and_runtime_lock(self):
        dockerfile = (MONOREPO_ROOT / "docker" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        runner = (MONOREPO_ROOT / "docker" / "run_mkmini_dev.sh").read_text(
            encoding="utf-8"
        )
        host_runner = (
            MONOREPO_ROOT / "docker" / "start_real_robot_neupan.sh"
        ).read_text(encoding="utf-8")
        preflight = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "mkmini_neupan_bringup"
            / "thor_neupan_preflight_node.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "ARG PYTORCH_BASE_IMAGE=nvcr.io/nvidia/pytorch:26.06-py3",
            dockerfile,
        )
        self.assertIn("FROM ${PYTORCH_BASE_IMAGE}", dockerfile)
        self.assertIn("AS neupan-core", dockerfile)
        self.assertIn("FROM neupan-core AS nav2-planner", dockerfile)
        self.assertIn("FROM nav2-planner AS full-debug", dockerfile)
        self.assertIn("FROM neupan-core AS dev", dockerfile)
        self.assertIn(
            "ARG UBUNTU_PORTS_MIRROR=https://mirrors.ustc.edu.cn/ubuntu-ports",
            dockerfile,
        )
        self.assertIn(
            "ARG ROS2_APT_MIRROR=https://mirrors.ustc.edu.cn/ros2/ubuntu",
            dockerfile,
        )
        self.assertIn('Acquire::Retries', dockerfile)
        self.assertIn('Proxy::${APT_MIRROR_HOST}', dockerfile)
        self.assertGreaterEqual(dockerfile.count("apt-get install -y"), 3)
        self.assertIn(
            "ENV LD_LIBRARY_PATH=/opt/hpcx/ompi/lib:/opt/hpcx/ucx/lib:${LD_LIBRARY_PATH}",
            dockerfile,
        )
        self.assertIn("ros-${ROS_DISTRO}-ros-base", dockerfile)
        self.assertIn("python3-tk", dockerfile)
        self.assertIn(
            "ARG LIVOX_SDK2_COMMIT=f5d9375f84efe2b15bc0a052d3e18482ed13adf4",
            dockerfile,
        )
        self.assertIn("https://github.com/Livox-SDK/Livox-SDK2.git", dockerfile)
        self.assertIn(
            "ARG LIVOX_SDK2_ARCHIVE_SHA256="
            "f469dc57b38cd64c71381eb54d9525bfc3574feb0152c2b65239283107c4fa29",
            dockerfile,
        )
        self.assertIn("COPY Livox-SDK2-f5d9375", dockerfile)
        self.assertIn("sha256sum -c -", dockerfile)
        self.assertIn('-DCMAKE_CXX_FLAGS="-include cstdint"', dockerfile)
        self.assertNotIn("RUN git clone", dockerfile)
        self.assertIn("cmake --install", dockerfile)
        self.assertIn("liblivox_lidar_sdk_shared.so", dockerfile)
        self.assertIn("import torch", dockerfile)
        self.assertIn("/etc/mkmini/thor-runtime.lock.json", dockerfile)
        self.assertIn("torch.cuda.is_available()", dockerfile)

        self.assertIn("--runtime nvidia", runner)
        self.assertIn("NVIDIA_VISIBLE_DEVICES=all", runner)
        self.assertIn("NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,video", runner)
        self.assertIn('RUNTIME_MANIFEST="/etc/mkmini/thor-runtime.lock.json"', runner)
        self.assertIn("MKMINI_THOR_RUNTIME_MANIFEST=${RUNTIME_MANIFEST}", runner)
        self.assertIn("torch.cuda.is_available()", runner)
        self.assertIn("IMAGE_RUNTIME_MANIFEST", preflight)
        self.assertIn("--runtime nvidia", host_runner)
        self.assertIn("MKMINI_THOR_RUNTIME_MANIFEST", host_runner)

        bootstrap = (WORKSPACE_ROOT / "scripts" / "bootstrap_jazzy.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("ldconfig -p", bootstrap)
        self.assertIn("liblivox_lidar_sdk_shared.so", bootstrap)

    def test_neupan_launch_fails_fast_without_package_or_checkpoint(self):
        launch_file = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "launch"
            / "neupan.launch.py"
        ).read_text(encoding="utf-8")

        self.assertIn("get_package_share_directory", launch_file)
        self.assertIn("load_neupan_config_paths", launch_file)
        self.assertIn("robot_config_dir", launch_file)
        self.assertIn("RuntimeError", launch_file)

    def test_full_stack_can_pass_custom_neupan_config_to_neupan_launch(self):
        launch_file = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "launch"
            / "full_stack.launch.py"
        ).read_text(encoding="utf-8")
        neupan_launch_file = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "launch"
            / "neupan.launch.py"
        ).read_text(encoding="utf-8")

        self.assertIn('DeclareLaunchArgument("neupan_config", default_value="")', launch_file)
        self.assertIn('"neupan_config": neupan_config', launch_file)
        self.assertIn('DeclareLaunchArgument("neupan_config", default_value=default_config)', neupan_launch_file)
        self.assertIn('if not config_path:', neupan_launch_file)

    def test_docker_test_runner_returns_failure_when_tests_fail(self):
        script = (
            MONOREPO_ROOT
            / "docker"
            / "scripts"
            / "run_tests.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("set -euo pipefail", script)
        self.assertIn("colcon test --packages-select yhs_can_interfaces yhs_can_control", script)
        self.assertIn("--return-code-on-test-failure", script)
        self.assertIn("colcon test-result --verbose", script)
        self.assertIn('python3 -m pytest "${test_dir}" -v', script)
        self.assertNotIn("--return-code-on-test-failure || true", script)
        self.assertNotIn("colcon test-result --verbose || true", script)
        self.assertNotIn('python3 -m pytest "${test_dir}" -v ||', script)
        self.assertNotIn("PASS=0", script)
        self.assertNotIn("FAIL=0", script)

    def test_stack_check_rejects_missing_neupan_frequency_and_duplicate_control_publishers(self):
        script = (WORKSPACE_ROOT / "scripts" / "check_stack.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn('timeout 6s ros2 topic hz "$topic" --window 50', script)
        self.assertNotIn("ros2 topic hz /neupan_cmd_vel --window 50 || true", script)
        self.assertIn("ros2 topic info /ctrl_cmd", script)
        self.assertIn("Publisher count: 1", script)
        self.assertIn("cmd_vel_to_ctrl_cmd_node", script)
        self.assertIn("/veh_diag_fb", script)
        self.assertIn("check_topic_hz /neupan_cmd_vel", script)
        self.assertIn("check_topic_hz /neupan/ackermann_cmd", script)
        self.assertIn("check_topic_hz /veh_diag_fb 2.0", script)
        self.assertIn("rate >= min_rate", script)

    def test_acceptance_recording_captures_dedicated_diagnostic_topic(self):
        script = (
            WORKSPACE_ROOT / "scripts" / "record_acceptance_run.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("/veh_diag_fb", script)

    def test_runtime_check_treats_missing_checkpoint_as_hard_failure(self):
        script = (WORKSPACE_ROOT / "scripts" / "check_neupan_runtime.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("check_neupan_config", script)
        self.assertIn("check_cvxpylayer_autograd", script)
        self.assertIn("--require-checkpoint", script)

    def test_thor_preflight_command_is_documented_before_neupan_launch(self):
        readme = (WORKSPACE_ROOT / "README.md").read_text(encoding="utf-8")
        safety_checklist = (
            WORKSPACE_ROOT / "docs" / "safety-checklist.md"
        ).read_text(encoding="utf-8")
        setup_py = (
            WORKSPACE_ROOT
            / "src"
            / "mkmini_neupan_bringup"
            / "setup.py"
        ).read_text(encoding="utf-8")

        self.assertIn("thor_neupan_preflight", setup_py)
        self.assertIn(
            "ros2 run mkmini_neupan_bringup thor_neupan_preflight",
            readme,
        )
        self.assertIn(
            "ros2 launch mkmini_neupan_bringup full_stack.launch.py",
            readme,
        )
        self.assertIn(
            "ros2 run mkmini_neupan_bringup thor_neupan_preflight",
            safety_checklist,
        )

    def test_real_robot_one_click_scripts_are_safe_contracts(self):
        host_script = (
            MONOREPO_ROOT / "docker" / "start_real_robot_neupan.sh"
        ).read_text(encoding="utf-8")
        container_runner = (
            WORKSPACE_ROOT / "scripts" / "start_real_robot_neupan.sh"
        ).read_text(encoding="utf-8")
        combined = host_script + "\n" + container_runner

        self.assertIn("/.dockerenv", host_script)
        self.assertIn("MKMINI_IN_CONTAINER", host_script)
        self.assertIn("docker exec", host_script)
        self.assertIn("docker run", host_script)
        self.assertIn("--network host", host_script)
        self.assertIn("--privileged", host_script)
        self.assertIn("CAN_IFACE", host_script)
        self.assertIn("LIDAR_HOST_CIDR", host_script)
        self.assertIn("thor_neupan_preflight", container_runner)
        self.assertIn(
            "ros2 launch mkmini_neupan_bringup full_stack.launch.py",
            container_runner,
        )
        self.assertIn("start_neupan:=true", container_runner)
        self.assertIn("disarm_bridge.sh", container_runner)
        self.assertIn("start_neupan:=*", container_runner)
        cleanup_start = container_runner.index("cleanup() {")
        self.assertLess(
            container_runner.index("disarm_bridge_once", cleanup_start),
            container_runner.index('kill -INT "${LAUNCH_PID}"', cleanup_start),
        )
        self.assertNotIn("arm_bridge.sh I_HAVE_REMOTE_AND_ESTOP", combined)
        self.assertNotIn("bash scripts/arm_bridge.sh", combined)

    def test_real_robot_one_click_launch_is_documented(self):
        docker_readme = (MONOREPO_ROOT / "docker" / "README.md").read_text(
            encoding="utf-8"
        )
        readme = (WORKSPACE_ROOT / "README.md").read_text(encoding="utf-8")
        safety_checklist = (
            WORKSPACE_ROOT / "docs" / "safety-checklist.md"
        ).read_text(encoding="utf-8")

        self.assertIn("bash docker/start_real_robot_neupan.sh", docker_readme)
        self.assertIn(
            "bash docker/start_real_robot_neupan.sh --dry-run",
            docker_readme,
        )
        self.assertIn(
            "bash /workspaces/MK-mini_ws/neupan_mkmini_ws/scripts/start_real_robot_neupan.sh --dry-run",
            docker_readme,
        )
        self.assertIn("bash docker/start_real_robot_neupan.sh", readme)
        self.assertIn("bash scripts/start_real_robot_neupan.sh --dry-run", readme)
        self.assertIn("bash docker/start_real_robot_neupan.sh", safety_checklist)
        self.assertIn("不会自动解锁", safety_checklist)

    def test_neupan_output_frequency_is_post_launch_acceptance_only(self):
        checklist = (
            WORKSPACE_ROOT / "docs" / "safety-checklist.md"
        ).read_text(encoding="utf-8")
        preflight_section = checklist.split("## NeuPAN 启动前附加检查", 1)[1].split(
            "## NeuPAN 启动后验收",
            1,
        )[0]
        post_launch_section = checklist.split("## NeuPAN 启动后验收", 1)[1]

        self.assertNotIn("/neupan_cmd_vel", preflight_section)
        self.assertNotIn("/neupan/ackermann_cmd", preflight_section)
        self.assertIn("/neupan_cmd_vel", post_launch_section)
        self.assertIn("/neupan/ackermann_cmd", post_launch_section)

    def test_import_upstreams_script_imports_all_required_sources(self):
        script = (WORKSPACE_ROOT / "scripts" / "import_upstreams.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn('repos_file="mkmini_neupan.lock.repos"', script)
        self.assertIn('vcs import . < "${repos_file}"', script)
        self.assertIn("bash scripts/freeze_revisions.sh", script)
        self.assertIn("src/neupan_ros2", script)
        self.assertIn("src/livox_ros_driver2", script)
        self.assertIn("src/FAST_LIO", script)
        self.assertIn("third_party/NeuPAN", script)
        self.assertIn("MKMINI_VENDOR_SRC", script)
        self.assertIn("src/yhs_can_control", script)
        self.assertIn("src/yhs_can_interfaces", script)

    def test_bootstrap_requires_imported_neupan_sources_before_build(self):
        script = (WORKSPACE_ROOT / "scripts" / "bootstrap_jazzy.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("src/neupan_ros2", script)
        self.assertIn("src/livox_ros_driver2", script)
        self.assertIn("src/FAST_LIO", script)
        self.assertIn("third_party/NeuPAN", script)
        self.assertIn("bash scripts/import_upstreams.sh /path/to/ROS2_MK-mini/src", script)

    def test_core_bootstrap_prepares_livox_jazzy_and_uses_system_mpi(self):
        script = (WORKSPACE_ROOT / "scripts" / "bootstrap_jazzy.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("package_ROS2.xml", script)
        self.assertIn("launch_ROS2", script)
        self.assertIn("src/neupan_ros2/src/neupan_ros2", script)
        self.assertNotIn("rosdep install --from-paths src --ignore-src", script)
        self.assertIn("--packages-skip ddr_minimal_sim", script)
        self.assertIn("unset OPAL_PREFIX OPAL_DESTDIR", script)
        self.assertIn("-DROS_EDITION=ROS2", script)
        self.assertIn("-DDISTRO_ROS=jazzy", script)
        self.assertIn("-DMPI_C_COMPILER=/usr/bin/mpicc", script)
        self.assertIn("-DMPI_CXX_COMPILER=/usr/bin/mpicxx", script)


if __name__ == "__main__":
    unittest.main()
