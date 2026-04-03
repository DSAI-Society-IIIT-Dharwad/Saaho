"""
Manual goal publisher for testing.
Run this and enter goal coordinates to test the robot.
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
import sys


def main():
    rclpy.init()
    node = Node("manual_goal_pub")
    pub = node.create_publisher(PoseStamped, "/goal", 10)
    
    print("\n" + "="*60)
    print(" Manual Goal Publisher")
    print("="*60)
    print("\nEnter goal coordinates (or Ctrl+C to quit)")
    print("Examples: '2 2', '-1 1', '0.5 -0.5'")
    print()
    
    try:
        while True:
            try:
                line = input("Goal (x y): ").strip()
                if not line:
                    continue
                
                parts = line.split()
                if len(parts) != 2:
                    print("❌ Need two numbers: x y")
                    continue
                
                x, y = float(parts[0]), float(parts[1])
                
                msg = PoseStamped()
                msg.header.frame_id = "odom"
                msg.header.stamp = node.get_clock().now().to_msg()
                msg.pose.position.x = x
                msg.pose.position.y = y
                msg.pose.position.z = 0.0
                msg.pose.orientation.w = 1.0
                
                pub.publish(msg)
                print(f"✅ Published goal: ({x:.2f}, {y:.2f})")
                
            except ValueError:
                print("❌ Invalid numbers")
            except EOFError:
                break
    
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    
    print("\n[Stopped]")


if __name__ == "__main__":
    main()
