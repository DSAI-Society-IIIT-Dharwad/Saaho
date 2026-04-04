#!/bin/bash
# Quick test - 50 episodes with random goals on original world

set -e

echo "=== Quick Diverse Training Test ==="
echo "Episodes: 50"
echo "Random goals: YES"
echo ""

# Kill existing
docker exec ros2_container bash -c 'killall -9 gzserver gzclient python3 2>/dev/null; true'
sleep 3

# Start Gazebo with original world  
echo "Starting Gazebo..."
docker exec -d ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    export LIBGL_ALWAYS_SOFTWARE=1
    source /opt/ros/humble/setup.bash
    gzserver /opt/ros/humble/share/turtlebot3_gazebo/worlds/turtlebot3_world.world \
        -s libgazebo_ros_init.so \
        -s libgazebo_ros_factory.so \
        -s libgazebo_ros_force_system.so
"

sleep 12

# Spawn robot
echo "Spawning robot..."
docker exec ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    source /opt/ros/humble/setup.bash
    timeout 20 ros2 run gazebo_ros spawn_entity.py \
        -entity burger \
        -file /opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf \
        -x -2.0 -y -0.5 -z 0.01 2>/dev/null || true
"

sleep 5

# Train
echo "Training 50 episodes..."
docker exec ros2_container bash -c "
    cd /root/drone_rl
    source /opt/ros/humble/setup.bash
    python3 train_td3.py \
        --episodes 50 \
        --random-goals \
        --model-name model_td3_test.pt
"

echo ""
echo "✅ Test complete!"
