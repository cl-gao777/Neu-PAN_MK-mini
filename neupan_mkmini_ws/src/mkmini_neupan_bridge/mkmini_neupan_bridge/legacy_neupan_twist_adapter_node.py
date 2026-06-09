from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node

from .adapters import legacy_neupan_action_to_ackermann


class LegacyNeuPANTwistAdapterNode(Node):
    """Makes the upstream NeuPAN Ackermann Twist semantics explicit."""

    def __init__(self) -> None:
        super().__init__("legacy_neupan_twist_adapter")
        input_topic = self.declare_parameter(
            "input_topic", "/neupan_cmd_vel"
        ).value
        output_topic = self.declare_parameter(
            "output_topic", "/neupan/ackermann_cmd"
        ).value
        frame_id = self.declare_parameter("frame_id", "base_link").value
        self._frame_id = frame_id
        self._publisher = self.create_publisher(
            AckermannDriveStamped, output_topic, 10
        )
        self.create_subscription(Twist, input_topic, self._callback, 10)
        self.get_logger().warn(
            "Compatibility mode: interpreting Twist.angular.z as steering angle "
            "in radians, not yaw rate. Do not connect this topic to cmd_vel."
        )

    def _callback(self, message: Twist) -> None:
        command = legacy_neupan_action_to_ackermann(
            float(message.linear.x), float(message.angular.z)
        )
        output = AckermannDriveStamped()
        output.header.stamp = self.get_clock().now().to_msg()
        output.header.frame_id = self._frame_id
        output.drive.speed = command.speed_mps
        output.drive.steering_angle = command.steering_rad
        self._publisher.publish(output)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = LegacyNeuPANTwistAdapterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
