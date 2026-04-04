#!/bin/bash
# Start Gazebo, RViz, and demo with the diverse model

set -e

echo "=================================================="
echo " 🚀 Starting Demo with Diverse Model"
echo "=================================================="
echo ""

# Clean up
echo "🧹 Cleaning up previous processes..."
docker exec ros2_container bash -c 'killall -9 gzserver gzclient rviz2 python3 2>/dev/null; exit 0'
sleep 3

# Start Gazebo
echo "⏳ Starting Gazebo..."
docker exec -d ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    export LIBGL_ALWAYS_SOFTWARE=1
    source /opt/ros/humble/setup.bash
    gzserver /opt/ros/humble/share/turtlebot3_gazebo/worlds/turtlebot3_world.world \
        -s libgazebo_ros_init.so \
        -s libgazebo_ros_factory.so \
        -s libgazebo_ros_force_system.so
"

sleep 10

# Start Gazebo GUI
echo "🖥️  Starting Gazebo GUI..."
DISPLAY=:0 docker exec -d ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    export LIBGL_ALWAYS_SOFTWARE=1
    source /opt/ros/humble/setup.bash
    gzclient
"

sleep 3

# Spawn robot
echo "🤖 Spawning TurtleBot3..."
docker exec ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    source /opt/ros/humble/setup.bash
    timeout 20 ros2 run gazebo_ros spawn_entity.py \
        -entity burger \
        -file /opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf \
        -x -2.0 -y -0.5 -z 0.01 2>/dev/null || true
"

sleep 5

# Set Gazebo camera to follow robot
echo "📷 Setting camera view..."
docker exec ros2_container bash -c "
    source /opt/ros/humble/setup.bash
    gz camera -c user_camera -f burger 2>/dev/null || true
"

# Start RViz
echo "📊 Starting RViz..."
DISPLAY=:0 docker exec -d ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    source /opt/ros/humble/setup.bash
    rviz2 -d /root/rviz_config.rviz
"

sleep 5

# Start demo with DIVERSE model
echo "🎯 Starting demo with diverse model..."
echo ""
docker exec ros2_container bash -c "
    cd /root/drone_rl
    source /opt/ros/humble/setup.bash
    python3 demo_trained_agent.py --model model_td3_diverse.pt
"

echo ""
echo "✅ Demo started with diverse model!"
echo ""
echo "Instructions:"
echo "  1. Gazebo and RViz are now running"
echo "  2. In RViz, use '2D Goal Pose' tool to set goals"
echo "  3. Robot will navigate using the diverse trained model"
echo "  4. Try different goal positions to test generalization!"
echo ""
