#!/bin/bash
# Start demo with Layout 2 (scattered obstacles - 8 cylinders)

echo "Starting with Layout 2 (Scattered Obstacles)..."
echo ""

# Start Gazebo with Layout 2
docker exec -d ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    export LIBGL_ALWAYS_SOFTWARE=1
    source /opt/ros/humble/setup.bash
    gzserver /root/custom_worlds/turtlebot3_layout1.world \
        -s libgazebo_ros_init.so \
        -s libgazebo_ros_factory.so \
        -s libgazebo_ros_force_system.so
"

echo "Waiting for Gazebo..."
sleep 12

# Start GUI
DISPLAY=:0 docker exec -d ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    export LIBGL_ALWAYS_SOFTWARE=1
    source /opt/ros/humble/setup.bash
    gzclient
"

sleep 3

# Spawn robot
docker exec ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    source /opt/ros/humble/setup.bash
    ros2 run gazebo_ros spawn_entity.py \
        -entity burger \
        -file /opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf \
        -x -2.0 -y -0.5 -z 0.01
" &

sleep 5

# Start RViz
DISPLAY=:0 docker exec -d ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    source /opt/ros/humble/setup.bash
    rviz2 -d /root/rviz_config.rviz
"

sleep 5

echo ""
echo "✅ Gazebo and RViz started with SCATTERED OBSTACLES layout!"
echo ""
echo "Now start the demo:"
echo "  docker exec ros2_container bash -c 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && python3 demo_trained_agent.py --model model_td3_diverse.pt'"
