from ackermann_msgs.msg import AckermannDriveStamped
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from std_msgs.msg import Bool
from tf2_ros import Buffer, TransformException, TransformListener
from yhs_can_interfaces.msg import CtrlCmd, VehDiagFb

from .adapters import chassis_feedback_is_healthy, timer_period_from_rate
from .safety import AckermannCommand, BridgeConfig, SafetyBridge


class AckermannSafetyBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("ackermann_safety_bridge")

        config = BridgeConfig(
            command_timeout_sec=self._param("command_timeout_sec", 0.3),
            feedback_timeout_sec=self._param("feedback_timeout_sec", 0.5),
            localization_timeout_sec=self._param("localization_timeout_sec", 0.3),
            max_speed_mps=self._param("max_speed_mps", 0.3),
            max_steering_deg=self._param("max_steering_deg", 25.0),
            allow_reverse=self._param("allow_reverse", False),
            forward_gear=self._param("forward_gear", 4),
            reverse_gear=self._param("reverse_gear", 2),
            require_feedback=self._param("require_feedback", True),
            require_localization=self._param("require_localization", True),
        )
        self._require_auto_can_mode = self._param("require_auto_can_mode", True)
        publish_rate_hz = self._param("publish_rate_hz", 50.0)
        input_topic = self._param("input_topic", "/neupan/ackermann_cmd")
        output_topic = self._param("output_topic", "/ctrl_cmd")
        arm_topic = self._param("arm_topic", "/neupan/drive_enable")
        emergency_stop_topic = self._param(
            "emergency_stop_topic", "/neupan/emergency_stop"
        )
        diagnostic_topic = self._param("diagnostic_topic", "/veh_diag_fb")
        status_topic = self._param("status_topic", "/neupan/safety_status")
        self._localization_target_frame = self._param(
            "localization_target_frame", "map"
        )
        self._localization_source_frame = self._param(
            "localization_source_frame", "base_link"
        )

        self._bridge = SafetyBridge(config)
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._last_reason = None
        self._command_publisher = self.create_publisher(CtrlCmd, output_topic, 10)
        self._status_publisher = self.create_publisher(DiagnosticArray, status_topic, 10)

        self.create_subscription(
            AckermannDriveStamped, input_topic, self._command_callback, 10
        )
        self.create_subscription(Bool, arm_topic, self._arm_callback, 10)
        self.create_subscription(
            Bool, emergency_stop_topic, self._emergency_stop_callback, 10
        )
        self.create_subscription(VehDiagFb, diagnostic_topic, self._diagnostic_callback, 10)
        self.create_timer(timer_period_from_rate(publish_rate_hz), self._publish_control)

        self.get_logger().warn(
            "Bridge starts DISARMED. Publish std_msgs/Bool true on "
            f"{arm_topic} only after the wheels-up safety check."
        )

    def _param(self, name, default):
        return self.declare_parameter(name, default).value

    def _now_sec(self) -> float:
        return self.get_clock().now().nanoseconds / 1_000_000_000.0

    def _command_callback(self, message: AckermannDriveStamped) -> None:
        command = AckermannCommand(
            speed_mps=float(message.drive.speed),
            steering_rad=float(message.drive.steering_angle),
        )
        self._bridge.update_command(command, self._now_sec())

    def _arm_callback(self, message: Bool) -> None:
        self._bridge.set_drive_enabled(bool(message.data), self._now_sec())

    def _emergency_stop_callback(self, message: Bool) -> None:
        self._bridge.set_emergency_stop(bool(message.data), self._now_sec())

    def _diagnostic_callback(self, diagnostic: VehDiagFb) -> None:
        healthy = chassis_feedback_is_healthy(
            fault_level=int(diagnostic.veh_fb_fault_level),
            auto_can_ctrl=bool(diagnostic.veh_fb_auto_can_ctrl_cmd),
            auxiliary_scram=bool(diagnostic.veh_fb_aux_scram),
            eps_fault=bool(diagnostic.veh_fb_eps_fault),
            require_auto_can_mode=self._require_auto_can_mode,
        )
        self._bridge.update_feedback(healthy, self._now_sec())

    def _publish_control(self) -> None:
        now = self.get_clock().now()
        now_sec = now.nanoseconds / 1_000_000_000.0
        self._update_localization_health(now_sec)
        decision = self._bridge.evaluate(now_sec)

        output = CtrlCmd()
        output.header.stamp = now.to_msg()
        output.ctrl_cmd_gear = decision.command.gear
        output.ctrl_cmd_velocity = decision.command.velocity_mps
        output.ctrl_cmd_steering = decision.command.steering_deg
        self._command_publisher.publish(output)

        if decision.reason != self._last_reason:
            if decision.reason == "active":
                self.get_logger().info("Ackermann safety bridge active")
            else:
                self.get_logger().warn(f"Publishing stop: {decision.reason}")
            self._last_reason = decision.reason
        self._publish_status(decision.reason)

    def _update_localization_health(self, now_sec: float) -> None:
        try:
            transform = self._tf_buffer.lookup_transform(
                self._localization_target_frame,
                self._localization_source_frame,
                Time(),
            )
        except TransformException:
            self._bridge.update_localization(False, now_sec)
            return

        stamp = transform.header.stamp
        transform_time_sec = float(stamp.sec) + float(stamp.nanosec) / 1_000_000_000.0
        age = now_sec - transform_time_sec
        healthy = 0.0 <= age <= self._bridge.config.localization_timeout_sec
        self._bridge.update_localization(healthy, now_sec)

    def _publish_status(self, reason: str) -> None:
        status = DiagnosticStatus()
        status.name = "mkmini_neupan_bridge"
        status.hardware_id = "mk-mini"
        status.level = (
            DiagnosticStatus.OK if reason == "active" else DiagnosticStatus.WARN
        )
        status.message = reason
        status.values = [KeyValue(key="reason", value=reason)]
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        array.status = [status]
        self._status_publisher.publish(array)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = AckermannSafetyBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
