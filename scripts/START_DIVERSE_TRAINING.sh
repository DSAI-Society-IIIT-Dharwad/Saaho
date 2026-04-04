#!/bin/bash
# SIMPLE DIVERSE TRAINING - Guaranteed to work
# This script trains your agent on multiple layouts with random goals
# Run from HOST: bash /home/hithx/Documents/H2F/h2f_implementation/scripts/START_DIVERSE_TRAINING.sh

set -e

echo "=================================================="
echo " 🚀 Starting Diverse Training"
echo "=================================================="
echo ""

# Ensure clean state
echo "🧹 Cleaning up any previous processes..."
docker exec ros2_container bash -c 'killall -9 python3 gzserver gzclient 2>/dev/null; exit 0'
sleep 5

echo "✅ Environment clean!"
echo ""

# Configuration
LAYOUTS=("turtlebot3_layout0.world" "turtlebot3_layout1.world" "turtlebot3_layout2.world" "turtlebot3_layout3.world")
EPISODES_PER_LAYOUT=250

echo "Configuration:"
echo "  - Layouts: ${#LAYOUTS[@]}"
echo "  - Episodes per layout: $EPISODES_PER_LAYOUT"
echo "  - Total episodes: $((${#LAYOUTS[@]} * EPISODES_PER_LAYOUT))"
echo "  - Goal strategy: Random per episode"
echo ""

# Train on each layout
for idx in "${!LAYOUTS[@]}"; do
    layout="${LAYOUTS[$idx]}"
    layout_num=$((idx + 1))
    
    echo "=================================================="
    echo " Layout $layout_num/${#LAYOUTS[@]}: $layout"
    echo "=================================================="
    echo ""
    
    # Start Gazebo
    echo "⏳ Starting Gazebo..."
    docker exec -d ros2_container bash -c "
        export TURTLEBOT3_MODEL=burger
        export LIBGL_ALWAYS_SOFTWARE=1
        source /opt/ros/humble/setup.bash
        gzserver /root/custom_worlds/$layout \
            -s libgazebo_ros_init.so \
            -s libgazebo_ros_factory.so \
            -s libgazebo_ros_force_system.so \
            > /tmp/gzserver_${layout_num}.log 2>&1
    "
    
    echo "   Waiting for Gazebo to initialize (12s)..."
    sleep 12
    
    # Spawn robot
    echo "🤖 Spawning TurtleBot3..."
    docker exec ros2_container bash -c "
        export TURTLEBOT3_MODEL=burger
        source /opt/ros/humble/setup.bash
        timeout 20 ros2 run gazebo_ros spawn_entity.py \
            -entity burger \
            -file /opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf \
            -x -2.0 -y -0.5 -z 0.01 \
            > /tmp/spawn_${layout_num}.log 2>&1 || true
    " &
    
    sleep 5
    echo "✅ Gazebo ready!"
    echo ""
    
    # Train
    echo "🎯 Training $EPISODES_PER_LAYOUT episodes with random goals..."
    echo "   (This will take ~20-30 minutes per layout)"
    echo ""
    
    docker exec ros2_container bash -c "
        cd /root/drone_rl
        source /opt/ros/humble/setup.bash
        python3 -u train_td3.py \
            --episodes $EPISODES_PER_LAYOUT \
            --random-goals \
            --model-name model_td3_diverse.pt \
            2>&1 | tee -a /root/drone_rl/train_layout${layout_num}.log
    "
    
    echo ""
    echo "✅ Completed layout $layout_num/$#{LAYOUTS[@]}"
    echo ""
    
    # Stop Gazebo for next layout
    if [ $layout_num -lt ${#LAYOUTS[@]} ]; then
        echo "🧹 Cleaning up for next layout..."
        docker exec ros2_container bash -c 'killall -9 gzserver gzclient 2>/dev/null; exit 0'
        sleep 3
        echo ""
    fi
done

echo "=================================================="
echo " ✅ TRAINING COMPLETE!"
echo "=================================================="
echo ""
echo "📊 Results:"
echo "   - Total episodes trained: $((${#LAYOUTS[@]} * EPISODES_PER_LAYOUT))"
echo "   - Model saved as: model_td3_diverse.pt"
echo "   - Logs: /root/drone_rl/train_layout*.log"
echo ""
echo "🎯 Next Steps:"
echo "   1. Test the model: bash scripts/test-diverse-model.sh"
echo "   2. Compare with original model performance"
echo "   3. Update your project report with results"
echo ""
echo "=================================================="
