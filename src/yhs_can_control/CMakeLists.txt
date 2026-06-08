cmake_minimum_required(VERSION 3.8)
project(yhs_can_control)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 查找控制节点需要的 ROS 2 依赖。
find_package(ament_cmake REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(yhs_can_interfaces REQUIRED)

# 协议层单独编译为库，方便节点和单元测试复用同一套 CAN 编解码逻辑。
add_library(mk_mini_protocol src/mk_mini_protocol.cpp)
target_include_directories(mk_mini_protocol PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(mk_mini_protocol PUBLIC cxx_std_17)

# 底盘 CAN 桥接节点：负责 SocketCAN 收发、底盘反馈解析、/odom 和 TF。
add_executable(yhs_can_control_node src/yhs_can_control_node.cpp)
target_include_directories(yhs_can_control_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(yhs_can_control_node PUBLIC c_std_99 cxx_std_17)
target_link_libraries(yhs_can_control_node mk_mini_protocol)
ament_target_dependencies(
  yhs_can_control_node
  tf2_ros
  tf2
  std_msgs
  rclcpp
  nav_msgs
  geometry_msgs
  yhs_can_interfaces
)

# Nav2 适配节点：把 /cmd_vel 转换成厂家底盘 /ctrl_cmd。
add_executable(cmd_vel_to_ctrl_cmd_node src/cmd_vel_to_ctrl_cmd_node.cpp)
target_include_directories(cmd_vel_to_ctrl_cmd_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(cmd_vel_to_ctrl_cmd_node PUBLIC cxx_std_17)
ament_target_dependencies(
  cmd_vel_to_ctrl_cmd_node
  rclcpp
  geometry_msgs
  yhs_can_interfaces
)

# 里程计精度测试工具：按目标距离发送低速 /cmd_vel，并用 /odom 判断停车。
add_executable(odom_distance_test_node src/odom_distance_test_node.cpp)
target_include_directories(odom_distance_test_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(odom_distance_test_node PUBLIC cxx_std_17)
ament_target_dependencies(
  odom_distance_test_node
  rclcpp
  geometry_msgs
  nav_msgs
  yhs_can_interfaces
)

install(TARGETS
  mk_mini_protocol
  yhs_can_control_node
  cmd_vel_to_ctrl_cmd_node
  odom_distance_test_node
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY include/
  DESTINATION include)

install(DIRECTORY launch params
  DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(ament_lint_auto REQUIRED)
  # 暂时跳过版权检查；后续补齐源码许可证声明后可以移除此设置。
  set(ament_cmake_copyright_FOUND TRUE)
  # 暂时跳过 cpplint；后续统一仓库风格和许可证信息后可以移除此设置。
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()

  ament_add_gtest(test_mk_mini_protocol test/test_mk_mini_protocol.cpp)
  target_link_libraries(test_mk_mini_protocol mk_mini_protocol)

  ament_add_gtest(test_odom_distance_test_logic test/test_odom_distance_test_logic.cpp)
  target_include_directories(test_odom_distance_test_logic PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)
endif()

ament_package()
