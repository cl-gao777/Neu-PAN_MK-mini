POINT_FIELDS = (
    ("x", 0),
    ("y", 4),
    ("z", 8),
    ("intensity", 12),
)


def iter_xyzi_points(custom_msg):
    for point in custom_msg.points:
        yield (
            float(point.x),
            float(point.y),
            float(point.z),
            float(point.reflectivity),
        )


def output_frame_id(custom_msg, configured_frame_id):
    if configured_frame_id:
        return configured_frame_id
    return custom_msg.header.frame_id


def _point_fields(point_field_type):
    return [
        point_field_type(
            name=name,
            offset=offset,
            datatype=point_field_type.FLOAT32,
            count=1,
        )
        for name, offset in POINT_FIELDS
    ]


def main(args=None):
    import rclpy
    from livox_ros_driver2.msg import CustomMsg
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import PointCloud2, PointField
    from sensor_msgs_py import point_cloud2

    class CustomMsgToPointCloud2(Node):
        def __init__(self):
            super().__init__("custom_msg_to_pointcloud2")
            self.declare_parameter("input_topic", "/livox/lidar")
            self.declare_parameter("output_topic", "/livox/points")
            self.declare_parameter("frame_id", "livox_frame")

            input_topic = (
                self.get_parameter("input_topic").get_parameter_value().string_value
            )
            output_topic = (
                self.get_parameter("output_topic").get_parameter_value().string_value
            )
            self._frame_id = (
                self.get_parameter("frame_id").get_parameter_value().string_value
            )
            self._fields = _point_fields(PointField)
            self._publisher = self.create_publisher(
                PointCloud2, output_topic, qos_profile_sensor_data
            )
            self.create_subscription(
                CustomMsg,
                input_topic,
                self._handle_custom_msg,
                qos_profile_sensor_data,
            )
            self.get_logger().info(
                f"Converting {input_topic} CustomMsg to {output_topic} PointCloud2"
            )

        def _handle_custom_msg(self, msg):
            header = msg.header
            header.frame_id = output_frame_id(msg, self._frame_id)
            cloud = point_cloud2.create_cloud(
                header,
                self._fields,
                iter_xyzi_points(msg),
            )
            self._publisher.publish(cloud)

    rclpy.init(args=args)
    node = CustomMsgToPointCloud2()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
