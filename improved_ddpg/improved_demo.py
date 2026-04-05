"""
improved_demo.py — Interactive Plug-and-Play Demo for the DDPG Agent.

You can set new goals dynamically directly inside the Gazebo/RViz simulation 
using the "2D Goal Pose" tool! The robot will instantly navigate towards it.
"""

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor, ExternalShutdownException
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist, PoseStamped, PointStamped
from std_srvs.srv import Empty
import numpy as np
import math
import os

from improved_agent_ddpg import DDPGAgent

# Same configuration defined in our DDPG environment
N_SCAN_SAMPLES = 180
COLLISION_DIST = 0.20
GOAL_RADIUS = 0.30


class InteractiveDemoNode(Node):
    def __init__(self, agent: DDPGAgent):
        super().__init__("interactive_ddpg_demo")
        self.agent = agent
        
        self.scan = None
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_yaw = 0.0
        # Default starting goal
        self.goal_x = 1.5
        self.goal_y = 1.5

        # Subscribers
        self.create_subscription(LaserScan, "/scan", self._scan_cb, 10)
        self.create_subscription(Odometry, "/odom", self._odom_cb, 10)
        # Listen for RViz 2D Goal Pose clicks!
        self.create_subscription(PoseStamped, "/goal_pose", self._goal_cb, 10)
        self.create_subscription(PoseStamped, "/move_base_simple/goal", self._goal_cb, 10)
        # Also listen to 'Publish Point' just in case the Goal tool is missing!
        self.create_subscription(PointStamped, "/clicked_point", self._point_cb, 10)
        
        # Publishers and Services
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.reset_client = self.create_client(Empty, "/reset_world")

        self.get_logger().info("✅ Interactive Demo Node ready!")
        self.get_logger().info("📍 Open RViz, click '2D Goal Pose', and place it anywhere to set a target.")

    def _scan_cb(self, msg):
        raw = np.array(msg.ranges, dtype=np.float32)
        self.scan = np.nan_to_num(raw, nan=3.5, posinf=3.5)

    def _odom_cb(self, msg):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.robot_yaw = math.atan2(siny, cosy)

    def _goal_cb(self, msg: PoseStamped):
        """Triggers instantly when you click using 2D Nav Goal in RViz."""
        self.goal_x = msg.pose.position.x
        self.goal_y = msg.pose.position.y
        self.get_logger().info(f"🎯 NEW GOAL RECEIVED: ({self.goal_x:.2f}, {self.goal_y:.2f})")

    def _point_cb(self, msg: PointStamped):
        """Triggers instantly when you click using Publish Point in RViz."""
        self.goal_x = msg.point.x
        self.goal_y = msg.point.y
        self.get_logger().info(f"📍 NEW LOCATION RECEIVED: ({self.goal_x:.2f}, {self.goal_y:.2f})")

    def get_state(self):
        if self.scan is None:
            return None
            
        # 180 LiDAR samples
        idx = np.linspace(0, len(self.scan) - 1, N_SCAN_SAMPLES, dtype=int)
        scan180 = (self.scan[idx] / 3.5).astype(np.float32)

        dist = math.hypot(self.goal_x - self.robot_x, self.goal_y - self.robot_y)
        angle = math.atan2(self.goal_y - self.robot_y, self.goal_x - self.robot_x) - self.robot_yaw
        angle = (angle + math.pi) % (2 * math.pi) - math.pi

        dist_norm = np.float32(dist / 4.0)
        angle_norm = np.float32(angle / math.pi)

        return np.append(scan180, [dist_norm, angle_norm])

    def check_done(self):
        if self.scan is None:
            return False, "run"
            
        min_dist = float(np.min(self.scan))
        dist_goal = math.hypot(self.goal_x - self.robot_x, self.goal_y - self.robot_y)

        if min_dist < COLLISION_DIST:
            self.get_logger().warn("💥 Collision detected! Resetting robot position...")
            return True, "collide"

        if dist_goal < GOAL_RADIUS:
            self.get_logger().info("⭐ Goal Reached! Waiting for you to click a new goal in RViz...")
            return True, "reach"

        return False, "run"

    def publish_action(self, action: np.ndarray):
        twist = Twist()
        # Bound limits just like the training logic
        twist.linear.x = float(np.clip(action[0], 0.0, 0.5))
        twist.angular.z = float(np.clip(action[1], -2.84, 2.84))
        self.cmd_pub.publish(twist)

    def stop(self):
        self.cmd_pub.publish(Twist())


def main():
    rclpy.init()
    
    # 180 scan samples + 2 goal coords = 182 state dim
    agent = DDPGAgent(state_dim=182, action_dim=2)
    
    model_file = "model_ddpg.pt"
    if os.path.exists(model_file):
        agent.load(model_file)
        print(f"Loaded trained weights from '{model_file}' ✅")
    else:
        print("⚠️ 'model_ddpg.pt' not found. Ensure the trained file is in this folder.")

    demo = InteractiveDemoNode(agent)
    executor = SingleThreadedExecutor()
    executor.add_node(demo)

    # Initial spin to load sensors
    executor.spin_once(timeout_sec=1.0)

    print("\n" + "="*60)
    print(" 🎮 Interactive TurtleBot3 DDPG Live Demonstration")
    print("="*60)
    print("  1. Open RViz")
    print("  2. Click '2D Goal Pose' in the top toolbar")
    print("  3. Click anywhere on the map to set a new destination")
    print("  4. Watch the DDPG model autonomously navigate there!")
    print("Press Ctrl+C to stop.\n")

    try:
        while rclpy.ok():
            state = demo.get_state()
            if state is None:
                executor.spin_once(timeout_sec=0.1)
                continue

            done, status = demo.check_done()
            
            if done:
                demo.stop()
                
                if status == "collide":
                    # Failsafe teleport back to start if crashed
                    demo.goal_x = 1.5
                    demo.goal_y = 1.5
                    if demo.reset_client.service_is_ready():
                        future = demo.reset_client.call_async(Empty.Request())
                        rclpy.spin_until_future_complete(demo, future, executor=executor, timeout_sec=1.0)
                    for _ in range(10): executor.spin_once(timeout_sec=0.01)
                else:
                    # Failsafe loop lock release: if reached goal, loop until goal changes
                    last_gx, last_gy = demo.goal_x, demo.goal_y
                    while rclpy.ok():
                        executor.spin_once(timeout_sec=0.1)
                        if abs(demo.goal_x - last_gx) > 0.05 or abs(demo.goal_y - last_gy) > 0.05:
                            break
            
            # Active navigation using purely learned exploitation (no noise)
            else:
                # Convert list to pure numpy array for pure Tensor format
                action = demo.agent.select_action(state)
                demo.publish_action(action)
                
                # Fast asynchronous execution loop for Gazebo
                executor.spin_once(timeout_sec=0.02)
                    
    except (KeyboardInterrupt, ExternalShutdownException):
        print("\nStopping demonstration module...")
    finally:
        demo.stop()
        executor.remove_node(demo)
        demo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()