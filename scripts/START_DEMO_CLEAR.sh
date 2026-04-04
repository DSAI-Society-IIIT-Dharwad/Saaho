#!/bin/bash
# Start demo with robot in CLEAR area (away from obstacles)

echo "🧹 Cleaning up..."
docker exec ros2_container bash -c 'killall -9 gzserver gzclient rviz2 python3 2>/dev/null; exit 0'
sleep 5

echo "🚀 Starting Gazebo..."
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

# Spawn robot in CLEAR area (away from obstacles)
echo "🤖 Spawning robot in clear area..."
docker exec ros2_container bash -c "
    export TURTLEBOT3_MODEL=burger
    source /opt/ros/humble/setup.bash
    ros2 run gazebo_ros spawn_entity.py \
        -entity burger \
        -file /opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf \
        -x 0.0 -y 0.0 -z 0.01
" &

sleep 5

echo "🖥️  Starting Gazebo GUI..."
DISPLAY=:0 docker exec -d ros2_container bash -c "
    export LIBGL_ALWAYS_SOFTWARE=1
    source /opt/ros/humble/setup.bash
    gzclient
"

sleep 3

echo "📊 Starting RViz..."
DISPLAY=:0 docker exec -d ros2_container bash -c "
    source /opt/ros/humble/setup.bash
    rviz2 -d /root/rviz_config.rviz
"

sleep 8

echo "🎯 Starting demo..."
docker exec -d ros2_container bash -c "
    cd /root/drone_rl
    source /opt/ros/humble/setup.bash
    python3 -u demo_continuous.py --model model_td3_diverse.pt > /tmp/demo.log 2>&1
"

sleep 5

echo ""
echo "✅ Demo ready! Robot spawned at (0, 0) - CLEAR AREA"
echo ""
echo "🎯 Try these goals in RViz:"
echo "   - (1.5, 1.5) - Upper right"
echo "   - (-1.5, -1.5) - Lower left"
echo "   - (1.0, -1.0) - Diagonal"
echo ""
echo "📊 Monitor: docker exec ros2_container tail -f /tmp/demo.log"
