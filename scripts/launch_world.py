"""
Flexible TurtleBot3 launch — accepts any world file.

Usage inside container:
  python3 launch_world.py open_world
  python3 launch_world.py turtlebot3_layout1
  python3 launch_world.py turtlebot3_house
  python3 launch_world.py turtlebot3_dqn_stage4
"""

import os
import sys
import subprocess

WORLDS_DIR = "/opt/ros/humble/share/turtlebot3_gazebo/worlds"
ROBOT_DESC = "/opt/ros/humble/share/turtlebot3_gazebo/urdf/turtlebot3_burger.urdf"

KNOWN = {
    "open":       "open_world.world",
    "open_world": "open_world.world",
    "hospital":   "hospital_world.world",
    "hospital_world": "hospital_world.world",
    "layout1":    "turtlebot3_layout1.world",
    "layout2":    "turtlebot3_layout2.world",
    "house":      "turtlebot3_house.world",
    "stage1":     "turtlebot3_dqn_stage1.world",
    "stage2":     "turtlebot3_dqn_stage2.world",
    "stage3":     "turtlebot3_dqn_stage3.world",
    "stage4":     "turtlebot3_dqn_stage4.world",
    "default":    "turtlebot3_world.world",
}

if len(sys.argv) < 2:
    print("Available worlds:")
    for k, v in KNOWN.items():
        print(f"  {k:15} → {v}")
    sys.exit(0)

key = sys.argv[1].lower()
world_file = KNOWN.get(key, key if key.endswith(".world") else key + ".world")
world_path = os.path.join(WORLDS_DIR, world_file)

if not os.path.exists(world_path):
    print(f"❌ World not found: {world_path}")
    sys.exit(1)

print(f"🌍 Launching world: {world_file}")
os.environ["TURTLEBOT3_MODEL"] = "burger"

cmd = [
    "ros2", "launch", "turtlebot3_gazebo", "turtlebot3_world.launch.py"
]

# Patch the world path directly via env override in gzserver
# Since launch file hardcodes it, we monkey-patch by replacing the file temporarily
backup = world_path + ".bak_default"
default_world = os.path.join(WORLDS_DIR, "turtlebot3_world.world")
backup_default = default_world + ".bak"

try:
    # Backup default world, replace with our target
    os.rename(default_world, backup_default)
    import shutil
    shutil.copy2(world_path, default_world)
    print(f"✅ World swapped. Starting Gazebo...")
    subprocess.run(cmd, env=os.environ)
finally:
    # Restore
    if os.path.exists(backup_default):
        os.rename(backup_default, default_world)
