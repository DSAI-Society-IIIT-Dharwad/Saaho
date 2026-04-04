#!/usr/bin/env bash
# Host: start ros2_container + full stack (same workloads as four manual terminals).
# Cursor/VS Code cannot open terminal tabs for you — run this once, or use Split
# Terminal and paste the "docker exec" lines this script prints.
set -euo pipefail

CONTAINER="${CONTAINER_NAME:-ros2_container}"
DISPLAY="${DISPLAY:-:0}"
export DISPLAY
# Default matches a plain container; use H2F_TRAIN_DIR=/workspace/drone_rl with compose bind mount.
TRAIN_DIR="${H2F_TRAIN_DIR:-/root/drone_rl}"

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

start_gui=1
start_rviz=1
start_train=1
while [[ "${1:-}" =~ ^- ]]; do
  case "$1" in
    --no-gui)  start_gui=0 ;;
    --no-rviz) start_rviz=0 ;;
    --no-train) start_train=0 ;;
    *) echo "Usage: $0 [--no-gui] [--no-rviz] [--no-train]" >&2; exit 1 ;;
  esac
  shift
done

if [[ "$start_gui" == 1 ]] || [[ "$start_rviz" == 1 ]]; then
  bash "${SCRIPT_ROOT}/scripts/host-allow-docker-x11.sh"
fi

docker start "${CONTAINER}" >/dev/null
docker exec "${CONTAINER}" bash -lc 'true' # wait until usable

ros_up() {
  docker exec "${CONTAINER}" bash -lc \
    'source /opt/ros/humble/setup.bash 2>/dev/null; ros2 node list 2>/dev/null' \
    | grep -q turtlebot3_laserscan
}

if ! ros_up; then
  echo "Starting Gazebo + TurtleBot3 (terminal 1)…"
  docker exec -d "${CONTAINER}" bash -lc \
    'source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && \
     ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py'
  for _ in $(seq 1 60); do
    if ros_up; then echo "Gazebo stack is up."; break; fi
    sleep 2
  done
  if ! ros_up; then
    echo "Timed out waiting for simulation. Check: docker logs ${CONTAINER}" >&2
    exit 1
  fi
else
  echo "Gazebo stack already running — skipping launch."
fi

if [[ "$start_gui" == 1 ]]; then
  if docker exec "${CONTAINER}" bash -lc 'pgrep -x gzclient >/dev/null 2>&1'; then
    echo "gzclient already running — skip."
  else
    echo "Starting gzclient (terminal 2)…"
    docker exec -d -e DISPLAY="$DISPLAY" "${CONTAINER}" bash -lc \
      'source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && gzclient'
  fi
fi

if [[ "$start_rviz" == 1 ]]; then
  if docker exec "${CONTAINER}" bash -lc 'pgrep -x rviz2 >/dev/null 2>&1'; then
    echo "rviz2 already running — skip."
  else
    echo "Starting rviz2 (terminal 3)…"
    docker exec -d -e DISPLAY="$DISPLAY" "${CONTAINER}" bash -lc \
      'source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && rviz2'
  fi
fi

if [[ "$start_train" == 1 ]]; then
  if docker exec "${CONTAINER}" bash -lc 'pgrep -f "python3.*train\\.py" >/dev/null 2>&1'; then
    echo "train.py already running — skip."
  else
    echo "Starting train.py (terminal 4)…"
    docker exec -d "${CONTAINER}" bash -lc \
      "cd ${TRAIN_DIR} && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && \
       (python3 -u train.py >> train.log 2>&1)"
  fi
fi

echo ""
echo "Done. Logs follow (training):"
echo "  docker exec -it ${CONTAINER} tail -f ${TRAIN_DIR}/train.log"
echo ""
echo "If you prefer four real terminals yourself, run each block separately:"
cat <<EOF

  # Terminal 1 — simulation
  docker exec -it ${CONTAINER} bash -lc 'source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py'

  # Terminal 2 — Gazebo GUI
  docker exec -it -e DISPLAY=$DISPLAY ${CONTAINER} bash -lc 'source /opt/ros/humble/setup.bash && gzclient'

  # Terminal 3 — RViz
  docker exec -it -e DISPLAY=$DISPLAY ${CONTAINER} bash -lc 'source /opt/ros/humble/setup.bash && rviz2'

  # Terminal 4 — RL
  docker exec -it ${CONTAINER} bash -lc "cd ${TRAIN_DIR} && source /opt/ros/humble/setup.bash && python3 train.py"
EOF
