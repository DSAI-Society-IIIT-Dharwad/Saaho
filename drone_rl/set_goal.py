"""
set_goal.py — Simple terminal goal setter for the TD3 demo.

Run this in a separate terminal and type coordinates to send goals to the robot.
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
import sys

class GoalPublisher(Node):
    def __init__(self):
        super().__init__("goal_setter")
        self.pub = self.create_publisher(PointStamped, "/goal", 10)
        self.get_logger().info("Goal setter ready")

    def send(self, x, y):
        msg = PointStamped()
        msg.header.frame_id = "odom"
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.point.x = float(x)
        msg.point.y = float(y)
        msg.point.z = 0.0
        self.pub.publish(msg)
        print(f"  ✅ Goal sent → ({x:.2f}, {y:.2f})")

def main():
    rclpy.init()
    node = GoalPublisher()

    print("\n" + "="*50)
    print("  TD3 Goal Setter")
    print("="*50)
    print("  Type: x y   (e.g.  1.5 1.0)")
    print("  Type: q     to quit")
    print("="*50)
    print("\n  Safe areas to try:")
    print("    1.5  1.5   (upper right)")
    print("   -1.5  1.5   (upper left)")
    print("    1.5 -1.5   (lower right)")
    print("   -1.5 -1.5   (lower left / near spawn)")
    print()

    while rclpy.ok():
        try:
            line = input("  Goal (x y) > ").strip()
            if line.lower() in ("q", "quit", "exit"):
                break
            parts = line.split()
            if len(parts) != 2:
                print("  ⚠  Enter two numbers, e.g.:  1.5 0.5")
                continue
            x, y = float(parts[0]), float(parts[1])
            node.send(x, y)
        except ValueError:
            print("  ⚠  Invalid numbers")
        except (KeyboardInterrupt, EOFError):
            break

    node.destroy_node()
    rclpy.shutdown()
    print("\n[Goal setter stopped]")

if __name__ == "__main__":
    main()
