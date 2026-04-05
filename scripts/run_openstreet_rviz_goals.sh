#!/usr/bin/env bash
# After zombie Gazebo piles up: restart container, then openstreet + RViz + bridge + demo.
# Run from repo root on the HOST.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DISPLAY="${DISPLAY:-:0}"
# Gazebo Classic often exits gzclient immediately without software GL inside Docker.
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export QT_X11_NO_MITSHM="${QT_X11_NO_MITSHM:-1}"

xhost +local:docker +local:root 2>/dev/null || true

echo "==> docker restart ros2_container (clears zombie gzserver/gzclient)"
docker restart ros2_container
sleep 12
docker exec ros2_container bash -lc 'true'

echo "==> sync world, launch, RViz config, Python nodes"
docker cp "$ROOT/worlds/openstreet.world" ros2_container:/opt/ros/humble/share/turtlebot3_gazebo/worlds/openstreet.world
docker cp "$ROOT/launch/turtlebot3_openstreet.launch.py" ros2_container:/root/turtlebot3_openstreet.launch.py
docker cp "$ROOT/launch/turtlebot3_open_street.launch.py" ros2_container:/root/turtlebot3_open_street.launch.py
docker cp "$ROOT/config/rviz_config.rviz" ros2_container:/workspace/config/rviz_config.rviz
docker cp "$ROOT/config/rviz_tb3_navigation2_openstreet.rviz" ros2_container:/workspace/config/rviz_tb3_navigation2_openstreet.rviz
docker cp "$ROOT/drone_rl/demo_continuous.py" ros2_container:/workspace/drone_rl/demo_continuous.py
docker cp "$ROOT/drone_rl/nav2_goal_bridge.py" ros2_container:/workspace/drone_rl/nav2_goal_bridge.py
docker cp "$ROOT/scripts/container/start_gzclient_gui.sh" ros2_container:/root/start_gzclient_gui.sh

echo "==> start Gazebo (openstreet) + TurtleBot3 (software GL: LIBGL_ALWAYS_SOFTWARE=$LIBGL_ALWAYS_SOFTWARE)"
docker exec \
  -e DISPLAY="$DISPLAY" \
  -e TURTLEBOT3_MODEL=burger \
  -e LIBGL_ALWAYS_SOFTWARE="$LIBGL_ALWAYS_SOFTWARE" \
  -e QT_X11_NO_MITSHM="$QT_X11_NO_MITSHM" \
  -d ros2_container bash -lc \
  'source /opt/ros/humble/setup.bash && ros2 launch /root/turtlebot3_openstreet.launch.py'

echo "==> wait for gzserver"
sleep 18
echo "==> Gazebo GUI: ros2 launch often drops gzclient under 'docker exec -d' — restart client with nohup"
docker exec \
  -e DISPLAY="$DISPLAY" \
  -e LIBGL_ALWAYS_SOFTWARE="$LIBGL_ALWAYS_SOFTWARE" \
  -e QT_X11_NO_MITSHM="$QT_X11_NO_MITSHM" \
  ros2_container bash -lc 'chmod +x /root/start_gzclient_gui.sh && /root/start_gzclient_gui.sh' || {
  echo "gzclient script failed — log:"
  docker exec ros2_container bash -lc 'tail -40 /tmp/gzclient.log 2>/dev/null || true'
}

echo "==> wait for sim (~15s more)"
sleep 15

echo "==> RViz"
docker exec \
  -e DISPLAY="$DISPLAY" \
  -e LIBGL_ALWAYS_SOFTWARE="$LIBGL_ALWAYS_SOFTWARE" \
  -e QT_X11_NO_MITSHM="$QT_X11_NO_MITSHM" \
  -d ros2_container bash -lc \
  'source /opt/ros/humble/setup.bash && rviz2 -d /workspace/config/rviz_tb3_navigation2_openstreet.rviz'

echo "==> nav2_goal_bridge + demo_continuous"
docker exec -d ros2_container bash -lc \
  'cd /workspace/drone_rl && source /opt/ros/humble/setup.bash && python3 -u nav2_goal_bridge.py'
docker exec -d ros2_container bash -lc \
  'cd /workspace/drone_rl && source /opt/ros/humble/setup.bash && python3 -u demo_continuous.py --model /workspace/trained_models/model_td3_diverse.pt'

sleep 3
docker exec ros2_container bash -lc 'echo "---"; pgrep -a gzserver | grep -v defunct | tail -2; pgrep -a gzclient | grep -v defunct || echo "NO gzclient"; pgrep -a rviz2 | head -1; pgrep -af nav2_goal_bridge | head -1; pgrep -af demo_continuous | head -1'

echo ""
echo "Done. Use RViz Fixed Frame: odom."
echo "  Nav2 '2D Goal Pose': open Navigation 2 panel, then use the goal tool."
echo "  Or use Set Goal / Publish Point (works with demo)."
echo "Gazebo GUI feels like it loads forever? Default is CPU rendering (LIBGL_ALWAYS_SOFTWARE=1) — it can sit at ~100% CPU and take minutes to feel responsive."
echo "  Try GPU:  LIBGL_ALWAYS_SOFTWARE=0 bash scripts/run_openstreet_rviz_goals.sh"
echo ""
echo "Full Nav2 map layout (slower):  rviz2 -d /workspace/config/rviz_tb3_navigation2_openstreet.rviz  inside the container."
echo ""
echo "No Gazebo window? 1) Alt+Tab / taskbar — title is often 'Gazebo'. 2) Check DISPLAY: echo \$DISPLAY (try :1)."
echo "  3) X11 test:  bash scripts/test_docker_x11.sh"
echo "  4) Client log: docker exec ros2_container tail -50 /tmp/gzclient.log"
