"""
spawn_object.py — Spawn / delete objects in Gazebo at runtime.

Usage (inside the container):
  python3 spawn_object.py box 1.5 2.0          # spawn a box at (1.5, 2.0)
  python3 spawn_object.py cylinder -1.0 3.0    # spawn a cylinder
  python3 spawn_object.py wall 0.0 2.5 --yaw 1.57  # spawn a wall rotated 90°
  python3 spawn_object.py delete my_box_3      # delete an object by name
  python3 spawn_object.py list                 # list all spawned objects

Interactive mode (no args):
  python3 spawn_object.py
"""

import rclpy
from rclpy.node import Node
from gazebo_msgs.srv import SpawnEntity, DeleteEntity, GetWorldProperties
import math
import sys
import argparse

# ── SDF templates ──────────────────────────────────────────────

def box_sdf(name, x, y, yaw=0.0,
            sx=0.5, sy=0.5, sz=0.5,
            r=0.2, g=0.5, b=0.8):
    return f"""<?xml version='1.0'?>
<sdf version='1.6'>
  <model name='{name}'>
    <static>true</static>
    <pose>{x} {y} {sz/2} 0 0 {yaw}</pose>
    <link name='link'>
      <collision name='col'>
        <geometry><box><size>{sx} {sy} {sz}</size></box></geometry>
      </collision>
      <visual name='vis'>
        <geometry><box><size>{sx} {sy} {sz}</size></box></geometry>
        <material>
          <ambient>{r} {g} {b} 1</ambient>
          <diffuse>{r} {g} {b} 1</diffuse>
        </material>
      </visual>
    </link>
  </model>
</sdf>"""


def cylinder_sdf(name, x, y, yaw=0.0,
                 radius=0.25, length=0.6,
                 r=0.9, g=0.3, b=0.1):
    return f"""<?xml version='1.0'?>
<sdf version='1.6'>
  <model name='{name}'>
    <static>true</static>
    <pose>{x} {y} {length/2} 0 0 {yaw}</pose>
    <link name='link'>
      <collision name='col'>
        <geometry><cylinder><radius>{radius}</radius><length>{length}</length></cylinder></geometry>
      </collision>
      <visual name='vis'>
        <geometry><cylinder><radius>{radius}</radius><length>{length}</length></cylinder></geometry>
        <material>
          <ambient>{r} {g} {b} 1</ambient>
          <diffuse>{r} {g} {b} 1</diffuse>
        </material>
      </visual>
    </link>
  </model>
</sdf>"""


def wall_sdf(name, x, y, yaw=0.0,
             length=1.5, thickness=0.15, height=0.8,
             r=0.7, g=0.7, b=0.7):
    return f"""<?xml version='1.0'?>
<sdf version='1.6'>
  <model name='{name}'>
    <static>true</static>
    <pose>{x} {y} {height/2} 0 0 {yaw}</pose>
    <link name='link'>
      <collision name='col'>
        <geometry><box><size>{length} {thickness} {height}</size></box></geometry>
      </collision>
      <visual name='vis'>
        <geometry><box><size>{length} {thickness} {height}</size></box></geometry>
        <material>
          <ambient>{r} {g} {b} 1</ambient>
          <diffuse>{r} {g} {b} 1</diffuse>
        </material>
      </visual>
    </link>
  </model>
</sdf>"""


# ── Spawner node ───────────────────────────────────────────────

class ObjectSpawner(Node):
    _counts = {}   # shape → count, for auto-naming

    def __init__(self):
        super().__init__("object_spawner")
        self.spawn_cli  = self.create_client(SpawnEntity,       "/spawn_entity")
        self.delete_cli = self.create_client(DeleteEntity,      "/delete_entity")
        self.props_cli  = self.create_client(GetWorldProperties,"/get_world_properties")

    def _wait(self, cli, timeout=5.0):
        if not cli.wait_for_service(timeout_sec=timeout):
            self.get_logger().error(f"Service {cli.srv_name} not available")
            return False
        return True

    def spawn(self, shape, x, y, yaw=0.0, name=None):
        shape = shape.lower()
        if name is None:
            c = ObjectSpawner._counts.get(shape, 0) + 1
            ObjectSpawner._counts[shape] = c
            name = f"{shape}_{c}"

        if   shape == "box":      sdf = box_sdf(name, x, y, yaw)
        elif shape == "cylinder": sdf = cylinder_sdf(name, x, y, yaw)
        elif shape == "wall":     sdf = wall_sdf(name, x, y, yaw)
        else:
            print(f"❌ Unknown shape '{shape}'. Use: box | cylinder | wall")
            return

        if not self._wait(self.spawn_cli):
            return

        req = SpawnEntity.Request()
        req.name            = name
        req.xml             = sdf
        req.robot_namespace = ""
        req.initial_pose.position.x = x
        req.initial_pose.position.y = y

        fut = self.spawn_cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=5.0)

        if fut.result() and fut.result().success:
            print(f"✅ Spawned '{name}' ({shape}) at ({x:.2f}, {y:.2f})  yaw={math.degrees(yaw):.0f}°")
        else:
            msg = fut.result().status_message if fut.result() else "timeout"
            print(f"❌ Spawn failed: {msg}")

    def delete(self, name):
        if not self._wait(self.delete_cli):
            return

        req = DeleteEntity.Request()
        req.name = name

        fut = self.delete_cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=5.0)

        if fut.result() and fut.result().success:
            print(f"🗑  Deleted '{name}'")
        else:
            msg = fut.result().status_message if fut.result() else "timeout"
            print(f"❌ Delete failed: {msg}")

    def list_objects(self):
        if not self._wait(self.props_cli):
            return

        fut = self.props_cli.call_async(GetWorldProperties.Request())
        rclpy.spin_until_future_complete(self, fut, timeout_sec=5.0)

        if fut.result():
            models = [m for m in fut.result().model_names
                      if m not in ("ground_plane", "turtlebot3_burger",
                                   "wall_north","wall_south","wall_east","wall_west")]
            if models:
                print("📦 Spawned objects:")
                for m in models:
                    print(f"   • {m}")
            else:
                print("📭 No custom objects spawned yet.")
        else:
            print("❌ Could not get world properties.")


# ── Interactive loop ───────────────────────────────────────────

HELP = """
Commands:
  box      <x> <y> [yaw_deg]      — spawn a blue box
  cylinder <x> <y> [yaw_deg]      — spawn an orange cylinder
  wall     <x> <y> [yaw_deg]      — spawn a grey wall segment
  delete   <name>                 — remove object by name  (e.g. box_1)
  list                            — show all spawned objects
  clear                           — delete ALL custom objects
  help                            — show this help
  quit / exit                     — exit

Examples:
  box 1.5 2.0
  cylinder -1 3 45
  wall 0 2.5 90
  delete cylinder_2
"""


def interactive(spawner):
    print("\n🏗  Object Spawner — interactive mode")
    print(HELP)
    while True:
        try:
            line = input("spawn> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue
        parts = line.split()
        cmd   = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            break
        elif cmd == "help":
            print(HELP)
        elif cmd == "list":
            spawner.list_objects()
        elif cmd == "clear":
            # list then delete each
            spawner.list_objects()
            # simple: just list, user can delete manually
            print("  (use 'delete <name>' to remove each one)")
        elif cmd in ("box", "cylinder", "wall"):
            if len(parts) < 3:
                print("  Usage: <shape> <x> <y> [yaw_deg]")
                continue
            try:
                x   = float(parts[1])
                y   = float(parts[2])
                yaw = math.radians(float(parts[3])) if len(parts) > 3 else 0.0
                spawner.spawn(cmd, x, y, yaw)
            except ValueError:
                print("  ❌ x and y must be numbers")
        elif cmd == "delete":
            if len(parts) < 2:
                print("  Usage: delete <name>")
            else:
                spawner.delete(parts[1])
        else:
            print(f"  ❓ Unknown command '{cmd}'. Type 'help'.")


# ── Entry point ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Spawn objects in Gazebo")
    parser.add_argument("shape",  nargs="?",
                        choices=["box","cylinder","wall","delete","list"],
                        help="Shape to spawn or action")
    parser.add_argument("x",     nargs="?", type=float)
    parser.add_argument("y",     nargs="?", type=float)
    parser.add_argument("--yaw", type=float, default=0.0,
                        help="Rotation in degrees (default 0)")
    parser.add_argument("--name", type=str, default=None)
    args = parser.parse_args()

    rclpy.init()
    spawner = ObjectSpawner()

    if args.shape is None:
        # Interactive mode
        interactive(spawner)
    elif args.shape == "list":
        spawner.list_objects()
    elif args.shape == "delete":
        if args.x is None:
            print("Usage: spawn_object.py delete <name>")
        else:
            spawner.delete(str(sys.argv[2]))
    else:
        if args.x is None or args.y is None:
            print(f"Usage: spawn_object.py {args.shape} <x> <y> [--yaw degrees]")
        else:
            spawner.spawn(args.shape, args.x, args.y,
                          math.radians(args.yaw), args.name)

    spawner.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
