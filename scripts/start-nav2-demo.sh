#!/usr/bin/env bash
# Complete setup for Nav2 Goal Pose testing
# Run this script to start everything properly

set -e

echo "=================================================="
echo " Starting TurtleBot3 TD3 Demo with Nav2 Goal"
echo "=================================================="
echo ""

# Step 1: Start Gazebo in background
echo "📦 Step 1/4: Starting Gazebo simulation..."
docker exec -d ros2_container bash -c 'source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && export LIBGL_ALWAYS_SOFTWARE=1 && ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py'

echo "   Waiting 12 seconds for Gazebo to initialize..."
sleep 12

# Step 2: Start Gazebo GUI
echo "📺 Step 2/4: Starting Gazebo GUI..."
xhost +local:docker 2>/dev/null || true
docker exec -d ros2_container bash -c 'export DISPLAY=:0 && export LIBGL_ALWAYS_SOFTWARE=1 && gzclient'

sleep 3

# Step 3: Start RViz
echo "🎨 Step 3/4: Starting RViz..."
docker exec -d ros2_container bash -c 'export DISPLAY=:0 && source /opt/ros/humble/setup.bash && rviz2'

sleep 3

# Step 4: Start trained agent demo
echo "🤖 Step 4/4: Starting trained TD3 agent..."
docker exec -d ros2_container bash -c 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && python3 demo_trained_agent.py'

sleep 3

echo ""
echo "=================================================="
echo " ✅ All Systems Running!"
echo "=================================================="
echo ""
echo "🎯 How to Use Nav2 Goal Pose in RViz:"
echo ""
echo "1. In RViz window:"
echo "   - Set Fixed Frame to 'odom' (top left)"
echo "   - Add LaserScan display: Topic = /scan"
echo "   - Add RobotModel display"
echo ""
echo "2. Click the Nav2 Goal button in toolbar"
echo "   - It should publish to /goal topic"
echo ""
echo "3. Click SAFE areas only:"
echo "   ✅ Top-right:    (1.5, 1.5)"
echo "   ✅ Top-left:     (-1.5, 1.5)"
echo "   ✅ Bottom-right: (1.5, -1.5)"
echo "   ✅ Bottom-left:  (-1.5, -1.5)"
echo ""
echo "   ❌ AVOID center (0, 0) - has obstacles!"
echo "   ❌ AVOID far edges > 3.0"
echo ""
echo "📊 Monitor logs:"
echo "   docker logs -f ros2_container"
echo ""
echo "🛑 To stop everything:"
echo "   docker exec ros2_container bash -c 'pkill -9 python3 gzclient rviz2 ros2 gzserver'"
echo ""
