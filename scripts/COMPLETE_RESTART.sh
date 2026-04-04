#!/bin/bash
# Complete restart - Gazebo, RViz, and Demo with Diverse Model

echo "=================================================="
echo " 🎯 Starting Complete Demo Setup"
echo "=================================================="
echo ""

# Kill everything
echo "🧹 Stopping all processes..."
docker exec ros2_container bash -c 'killall -9 gzserver gzclient rviz2 python3 2>/dev/null; exit 0'
sleep 5

# Start Gazebo
echo "🚀 Starting Gazebo with TurtleBot3 world..."
docker exec -d ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    export LIBGL_ALWAYS_SOFTWARE=1
    source /opt/ros/humble/setup.bash
    ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py
"

echo "   Waiting for Gazebo (20s)..."
sleep 20

# Start Gazebo GUI
echo "🖥️  Starting Gazebo GUI..."
DISPLAY=:0 docker exec -d ros2_container bash -c "
    export LIBGL_ALWAYS_SOFTWARE=1
    source /opt/ros/humble/setup.bash
    gzclient
"

sleep 5

# Start RViz
echo "📊 Starting RViz..."
DISPLAY=:0 docker exec -d ros2_container bash -c "
    source /opt/ros/humble/setup.bash
    rviz2 -d /root/rviz_config.rviz
"

sleep 8

# Start demo
echo "🎯 Starting Continuous Demo with Diverse Model..."
docker exec -d ros2_container bash -c "
    cd /root/drone_rl
    source /opt/ros/humble/setup.bash
    python3 -u demo_continuous.py --model model_td3_diverse.pt
"

sleep 5

echo ""
echo "=================================================="
echo " ✅ Everything is Running!"
echo "=================================================="
echo ""
echo "📋 What's Active:"
echo "   ✅ Gazebo (server + GUI)"
echo "   ✅ RViz (visualization)"
echo "   ✅ Continuous Demo (diverse model)"
echo ""
echo "🎯 How to Test:"
echo "   1. In RViz: Click '2D Goal Pose' tool"
echo "   2. Click and drag on the grid to set a goal"
echo "   3. Robot will navigate and STAY at goal"
echo "   4. Set new goals anytime!"
echo ""
echo "✨ Recommended First Goal: (0.5, 0.0)"
echo ""
echo "📊 Monitor demo output:"
echo "   docker exec ros2_container bash -c 'tail -f /tmp/demo_output.log'"
echo ""
echo "=================================================="
