#!/usr/bin/env bash
# Quick check: can the container draw on your screen? You should see a small clock for 4s.
set -euo pipefail
export DISPLAY="${DISPLAY:-:0}"
xhost +local:docker +local:root 2>/dev/null || true
echo "DISPLAY=$DISPLAY — you should see xclock from the container."
docker exec -e DISPLAY="$DISPLAY" ros2_container bash -lc 'command -v xclock >/dev/null || (apt-get update -qq && apt-get install -y -qq x11-apps)'
timeout 4 docker exec -e DISPLAY="$DISPLAY" ros2_container xclock -geometry 200x200+100+100 || true
echo "If you saw no clock, fix DISPLAY (try :0 or :1) or Wayland/X11 session."
