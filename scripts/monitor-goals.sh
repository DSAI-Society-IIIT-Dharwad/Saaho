#!/usr/bin/env bash
# Monitor all possible goal topics to see which one RViz publishes to

echo "🔍 Monitoring goal topics - set a goal in RViz now..."
echo ""

docker exec ros2_container bash -c '
source /opt/ros/humble/setup.bash

# Monitor multiple topics in parallel
(ros2 topic echo /goal 2>&1 | while read line; do echo "[/goal] $line"; done) &
(ros2 topic echo /goal_pose 2>&1 | while read line; do echo "[/goal_pose] $line"; done) &
(ros2 topic echo /move_base_simple/goal 2>&1 | while read line; do echo "[/move_base_simple/goal] $line"; done) &

# Wait
wait
'
