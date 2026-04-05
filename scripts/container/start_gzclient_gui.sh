#!/usr/bin/env bash
# Run inside container: stable gzclient (nohup + XDG_RUNTIME_DIR). Call from host via docker exec -e DISPLAY ...
# Note: no 'set -u' — ROS setup.bash touches unset vars.
set -eo pipefail
mkdir -p /tmp/runtime-root
chmod 700 /tmp/runtime-root
export XDG_RUNTIME_DIR=/tmp/runtime-root
# Defaults help Gazebo Classic + Qt inside Docker when the host does not pass these.
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export QT_X11_NO_MITSHM="${QT_X11_NO_MITSHM:-1}"
source /opt/ros/humble/setup.bash
pkill -x gzclient 2>/dev/null || true
sleep 1
: > /tmp/gzclient.log
nohup gzclient >> /tmp/gzclient.log 2>&1 &
echo "gzclient started PID=$! (log: /tmp/gzclient.log)"
sleep 2
pgrep -a gzclient || { echo "FAILED — tail log:"; tail -30 /tmp/gzclient.log; exit 1; }
