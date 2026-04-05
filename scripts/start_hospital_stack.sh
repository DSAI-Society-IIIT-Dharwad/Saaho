#!/usr/bin/env bash
# Start Gazebo (hospital world) + RViz + Nav2 bridge + TD3 demo.
# Prereq: docker compose up -d, xhost +local:docker
set -euo pipefail
xhost +local:docker +local:root 2>/dev/null || true

docker cp "$(dirname "$0")/../worlds/hospital_world.world" \
  ros2_container:/opt/ros/humble/share/turtlebot3_gazebo/worlds/hospital_world.world
docker cp "$(dirname "$0")/../launch/turtlebot3_hospital.launch.py" \
  ros2_container:/root/turtlebot3_hospital.launch.py

docker exec ros2_container bash -c '
  pkill -9 -f demo_continuous 2>/dev/null || true
  pkill -9 -f nav2_goal_bridge 2>/dev/null || true
  pkill -9 -f "ros2 launch" 2>/dev/null || true
  pkill -9 gzserver 2>/dev/null || true
  pkill -9 gzclient 2>/dev/null || true
  pkill -9 rviz2 2>/dev/null || true
  sleep 2
'

docker exec -e DISPLAY="${DISPLAY:-:0}" -e TURTLEBOT3_MODEL=burger -d ros2_container bash -c \
  'source /opt/ros/humble/setup.bash && ros2 launch /root/turtlebot3_hospital.launch.py'

sleep 28
docker exec -e DISPLAY="${DISPLAY:-:0}" -d ros2_container bash -c \
  'source /opt/ros/humble/setup.bash && rviz2 -d /workspace/config/rviz_config.rviz'
docker exec -d ros2_container bash -c \
  'cd /workspace/drone_rl && source /opt/ros/humble/setup.bash && python3 -u nav2_goal_bridge.py'
docker exec -d ros2_container bash -c \
  'cd /workspace/drone_rl && source /opt/ros/humble/setup.bash && python3 -u demo_continuous.py --model /workspace/trained_models/model_td3_diverse.pt'

echo "Hospital stack started. Gazebo should show cream walls + many rooms."
echo "Verify: docker exec ros2_container ps aux | grep gzserver"
