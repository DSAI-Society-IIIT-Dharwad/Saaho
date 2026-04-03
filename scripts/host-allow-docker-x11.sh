#!/usr/bin/env bash
# Run on the HOST (not inside Docker) before starting Gazebo GUI from a container.
set -euo pipefail
xhost +local:docker
echo "OK X11 access for local Docker. Ensure DISPLAY is set (e.g. export DISPLAY=:0)."
