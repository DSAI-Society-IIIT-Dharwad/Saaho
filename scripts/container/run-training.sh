#!/usr/bin/env bash
# Quick helper to switch between DQN and TD3 training inside container.

set -euo pipefail

MODE="${1:-td3}"

cd /root/drone_rl
set +u
source /opt/ros/humble/setup.bash
set -u
export TURTLEBOT3_MODEL=burger

case "$MODE" in
  dqn)
    echo "Starting DQN training (discrete actions)..."
    exec python3 -u train.py 2>&1 | tee train.log
    ;;
  td3)
    echo "Starting TD3 training (continuous actions)..."
    exec python3 -u train_td3.py 2>&1 | tee train_td3.log
    ;;
  *)
    echo "Usage: $0 {dqn|td3}" >&2
    exit 1
    ;;
esac
