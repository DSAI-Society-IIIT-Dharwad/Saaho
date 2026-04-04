#!/bin/bash
# Safe single-instance demo launcher

echo "🔍 Checking for existing demo processes..."
EXISTING=$(docker exec ros2_container bash -c 'pgrep -f demo_continuous 2>/dev/null | tr "\n" " "')
if [ -n "$EXISTING" ]; then
    echo "⚠  Found existing demo PIDs: $EXISTING — killing them..."
    docker exec ros2_container bash -c 'pkill -9 -f demo_continuous 2>/dev/null; exit 0'
    sleep 3
fi

echo "✅ Starting single demo instance..."
docker exec ros2_container bash -c 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && python3 -u demo_continuous.py --model model_td3_diverse.pt 2>&1'
