cmake_minimum_required(VERSION 3.8)
project(yhs_can_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 查找消息生成需要的 ROS 2 依赖。
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

# 生成 MK-mini 底盘自定义消息接口，供 yhs_can_control 发布和订阅。
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/BmsFlagInfoFb.msg"
  "msg/BmsInfoFb.msg"
  "msg/ChassisInfoFb.msg"
  "msg/CtrlCmd.msg"
  "msg/CtrlFb.msg"
  "msg/DriveMcuEcodeFb.msg"
  "msg/IoCmd.msg"
  "msg/IoFb.msg"
  "msg/LrWheelFb.msg"
  "msg/OdoFb.msg"
  "msg/RrWheelFb.msg"
  "msg/VehDiagFb.msg"
  "msg/Ultrasonic.msg"
  DEPENDENCIES std_msgs
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # 暂时跳过版权检查；后续补齐源码许可证声明后可以移除此设置。
  set(ament_cmake_copyright_FOUND TRUE)
  # 暂时跳过 cpplint；后续统一仓库风格和许可证信息后可以移除此设置。
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
