#!/bin/bash
# Quick diverse training - trains on multiple layouts sequentially

set -e

cd "$(dirname "$0")"

EPISODES_PER_LAYOUT=250

LAYOUTS=(
    "turtlebot3_layout0.world"
    "turtlebot3_layout1.world"
    "turtlebot3_layout2.world"
    "turtlebot3_layout3.world"
)

echo "============================================"
echo " Diverse TD3 Training"
echo "============================================"
echo " Layouts: ${#LAYOUTS[@]}"
echo " Episodes per layout: $EPISODES_PER_LAYOUT"
echo " Total: $((${#LAYOUTS[@]} * EPISODES_PER_LAYOUT)) episodes"
echo " Strategy: Random goals each episode"
echo "============================================"
echo ""

for idx in "${!LAYOUTS[@]}"; do
    layout="${LAYOUTS[$idx]}"
    layout_num=$((idx + 1))
    
    echo ""
    echo ">>> Layout $layout_num/${#LAYOUTS[@]}: $layout <<<"
    echo ""
    
    # Kill existing processes
    docker exec ros2_container bash -c 'killall -9 gzserver gzclient 2>/dev/null; true'
    sleep 3
    
    # Start Gazebo with this layout
    echo "Starting Gazebo..."
    docker exec -d ros2_container bash -c "
        export TURTLEBOT3_MODEL=burger
        export LIBGL_ALWAYS_SOFTWARE=1
        source /opt/ros/humble/setup.bash
        gzserver /root/custom_worlds/$layout \
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
    echo "Training $EPISODES_PER_LAYOUT episodes with random goals..."
    docker exec ros2_container bash -c "
        cd /root/drone_rl
        source /opt/ros/humble/setup.bash
        python3 train_td3.py \
            --episodes $EPISODES_PER_LAYOUT \
            --random-goals \
            --model-name model_td3_diverse.pt
    "
    
    echo "✅ Completed layout $layout_num"
done

echo ""
echo "============================================"
echo " ✅ Training Complete!"
echo "============================================"
echo " Model: model_td3_diverse.pt"
echo " Total episodes: $((${#LAYOUTS[@]} * EPISODES_PER_LAYOUT))"
echo "============================================"
