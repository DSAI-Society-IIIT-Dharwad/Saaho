#!/usr/bin/env bash
# Container: clean restart of Gazebo + TurtleBot3 spawn, following exact fix steps.
set -euo pipefail

echo "🟢 STEP 1 — Kill everything cleanly"
pkill -f gzserver || true
pkill -f gzclient || true
pkill -f 'python3.*train\.py' || true
sleep 2

echo "🟢 STEP 2 — Set model (REQUIRED for robot spawn)"
export TURTLEBOT3_MODEL=burger

echo "🟢 STEP 3 — Launch Gazebo properly"
set +u  # Allow unset vars during ROS sourcing
source /opt/ros/humble/setup.bash
set -u
echo "Starting ros2 launch in background..."
ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py &
LAUNCH_PID=$!

echo "👉 WAIT 10 seconds for Gazebo + robot spawn..."
sleep 10

echo "🟢 STEP 4 — Check robot spawned"
if ros2 topic list 2>/dev/null | grep -q '/cmd_vel'; then
  echo "✅ /cmd_vel exists — Robot spawned successfully"
else
  echo "⚠ Robot missing — spawning manually..."
  echo "🟢 STEP 5 — Spawn robot entity"
  ros2 run gazebo_ros spawn_entity.py \
    -entity turtlebot3 \
    -topic robot_description || echo "spawn_entity failed (may already exist)"
  sleep 3
  if ros2 topic list 2>/dev/null | grep -q '/cmd_vel'; then
    echo "✅ Robot now present"
  else
    echo "❌ Robot still missing — check Gazebo logs" >&2
    exit 1
  fi
fi

echo ""
echo "✅ Simulation ready. Launch process PID: ${LAUNCH_PID}"
echo "To stop simulation: kill ${LAUNCH_PID} or pkill -f gzserver"
echo ""
echo "🟢 STEP 6 — Run training AFTER this script completes."
echo "  In another terminal: docker exec -it ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 train.py'"
echo ""
echo "Gazebo is running in foreground now (Ctrl+C to stop)."
wait "${LAUNCH_PID}"
