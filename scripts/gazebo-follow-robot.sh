#!/usr/bin/env bash
# Reset Gazebo camera to view the robot
docker exec ros2_container bash -lc 'source /opt/ros/humble/setup.bash && gz camera -c user_camera -f burger'
