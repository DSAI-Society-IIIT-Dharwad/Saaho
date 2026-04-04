#!/bin/bash
# start-diverse-training.sh - Start TD3 training with multiple world layouts
# This script handles Gazebo management from the HOST side

set -e

LAYOUTS=(
    "turtlebot3_layout0.world"
    "turtlebot3_layout1.world"
    "turtlebot3_layout2.world"
    "turtlebot3_layout3.world"
)

EPISODES_PER_LAYOUT=250
TOTAL_LAYOUTS=${#LAYOUTS[@]}

echo "========================================"
echo " Diverse TD3 Training - Multiple Layouts"
echo "========================================"
echo ""
echo "Layouts: ${TOTAL_LAYOUTS}"
echo "Episodes per layout: ${EPISODES_PER_LAYOUT}"
echo "Total episodes: $((TOTAL_LAYOUTS * EPISODES_PER_LAYOUT))"
echo ""

# Function to start Gazebo with a specific world
start_gazebo() {
    local world_file=$1
    echo "🚀 Starting Gazebo with ${world_file}..."
    
    # Stop any existing Gazebo
    docker exec ros2_container bash -c 'killall -9 gzserver gzclient 2>/dev/null; true'
    sleep 3
    
    # Start Gazebo
    docker exec -d ros2_container bash -c "
        export TURTLEBOT3_MODEL=burger
        export LIBGL_ALWAYS_SOFTWARE=1
        source /opt/ros/humble/setup.bash
        gzserver /root/custom_worlds/${world_file} \
            -s libgazebo_ros_init.so \
            -s libgazebo_ros_factory.so \
            -s libgazebo_ros_force_system.so \
            > /tmp/gzserver.log 2>&1
    "
    
    sleep 10
    
    # Spawn robot
    docker exec ros2_container bash -c "
        export TURTLEBOT3_MODEL=burger
        source /opt/ros/humble/setup.bash
        ros2 run gazebo_ros spawn_entity.py \
            -entity burger \
            -file /opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf \
            -x -2.0 -y -0.5 -z 0.01 \
            > /tmp/spawn.log 2>&1
    " &
    
    sleep 5
    echo "✅ Gazebo ready with ${world_file}"
}

# Train on each layout
for idx in "${!LAYOUTS[@]}"; do
    layout=${LAYOUTS[$idx]}
    layout_num=$((idx + 1))
    
    echo ""
    echo "========================================"
    echo " Layout ${layout_num}/${TOTAL_LAYOUTS}: ${layout}"
    echo "========================================"
    
    start_gazebo "${layout}"
    
    # Run training for this layout
    echo "📚 Training ${EPISODES_PER_LAYOUT} episodes..."
    docker exec ros2_container bash -c "
        cd /root/drone_rl
        source /opt/ros/humble/setup.bash
        python3 train_td3.py \
            --episodes ${EPISODES_PER_LAYOUT} \
            --save-prefix layout${layout_num} \
            2>&1 | tee -a train_diverse_layout${layout_num}.log
    "
    
    echo "✅ Completed ${EPISODES_PER_LAYOUT} episodes on ${layout}"
done

echo ""
echo "========================================"
echo " ✅ All layouts trained!"
echo "========================================"
echo "Total episodes: $((TOTAL_LAYOUTS * EPISODES_PER_LAYOUT))"
echo "Model saved as: model_td3.pt"
