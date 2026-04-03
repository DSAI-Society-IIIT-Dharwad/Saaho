"""
demo_trained_agent.py — Continuous demo of trained TD3 agent.

The robot will navigate to goals repeatedly. You can:
- Watch in Gazebo GUI
- Set new goals in RViz using "2D Goal Pose" tool
- The agent uses the trained policy (no training, pure inference)
"""

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor, ExternalShutdownException
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist, PoseStamped
from std_srvs.srv import Empty
import numpy as np
import math
import torch

from agent_td3 import TD3Agent


# Copy of state computation from env.py
N_SCAN_SAMPLES = 24
COLLISION_DIST = 0.15
GOAL_RADIUS = 0.30


class DemoNode(Node):
    """Demo node that uses trained TD3 agent and listens to RViz goal poses."""
    
    def __init__(self, agent: TD3Agent):
        super().__init__("td3_demo")
        
        self.agent = agent
        
        # State
        self.scan = None
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_yaw = 0.0
        self.goal_x = 1.5
        self.goal_y = 1.5
        
        # ROS comms
        self.create_subscription(LaserScan, "/scan", self._scan_cb, 10)
        self.create_subscription(Odometry, "/odom", self._odom_cb, 10)
        self.create_subscription(PoseStamped, "/goal", self._goal_cb, 10)
        self.create_subscription(PoseStamped, "/goal_pose", self._goal_cb, 10)
        self.create_subscription(PoseStamped, "/move_base_simple/goal", self._goal_cb, 10)
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        
        self.reset_client = self.create_client(Empty, "/reset_world")
        
        self.get_logger().info("Demo node ready — listening for goals on /goal, /goal_pose, /move_base_simple/goal")
        self.get_logger().info(f"Current goal: ({self.goal_x:.2f}, {self.goal_y:.2f})")
    
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
        """Called when user sets 2D Goal Pose in RViz."""
        self.goal_x = msg.pose.position.x
        self.goal_y = msg.pose.position.y
        self.get_logger().info(f"🎯 New goal received: ({self.goal_x:.2f}, {self.goal_y:.2f})")
    
    def get_state(self):
        if self.scan is None:
            return None
        idx = np.linspace(0, len(self.scan) - 1, N_SCAN_SAMPLES, dtype=int)
        scan = (self.scan[idx] / 3.5).astype(np.float32)
        
        dist = math.hypot(self.goal_x - self.robot_x, self.goal_y - self.robot_y)
        angle = math.atan2(self.goal_y - self.robot_y, self.goal_x - self.robot_x) - self.robot_yaw
        angle = (angle + math.pi) % (2 * math.pi) - math.pi
        
        dist_norm = np.float32(dist / 4.0)
        angle_norm = np.float32(angle / math.pi)
        
        return np.append(scan, [dist_norm, angle_norm])
    
    def check_done(self):
        if self.scan is None:
            return False, 0.0
        
        min_dist = float(np.min(self.scan))
        dist_goal = math.hypot(self.goal_x - self.robot_x, self.goal_y - self.robot_y)
        
        if min_dist < COLLISION_DIST:
            self.get_logger().warn("💥 Collision!")
            return True, -200.0
        
        if dist_goal < GOAL_RADIUS:
            self.get_logger().info(f"🎯 Goal reached at ({self.goal_x:.2f}, {self.goal_y:.2f})!")
            return True, 200.0
        
        return False, 0.0
    
    def publish_action(self, action: np.ndarray):
        twist = Twist()
        twist.linear.x = float(np.clip(action[0], 0.0, 0.22))
        twist.angular.z = float(np.clip(action[1], -2.0, 2.0))
        self.cmd_pub.publish(twist)
    
    def stop(self):
        self.cmd_pub.publish(Twist())
    
    def reset(self, executor):
        self.scan = None
        self.stop()
        if self.reset_client.service_is_ready():
            future = self.reset_client.call_async(Empty.Request())
            rclpy.spin_until_future_complete(self, future, executor=executor, timeout_sec=3.0)
        for _ in range(20):
            executor.spin_once(timeout_sec=0.05)


def main_loop():
    rclpy.init()
    
    # Load trained agent
    agent = TD3Agent(state_dim=26, action_dim=2)
    agent.load("model_td3.pt")
    
    demo = DemoNode(agent)
    executor = SingleThreadedExecutor()
    executor.add_node(demo)
    
    # Initial spin
    executor.spin_once(timeout_sec=1.0)
    
    print("\n" + "="*60)
    print(" Trained TD3 Agent — Interactive Demo")
    print("="*60)
    print("\nControls:")
    print("  - Watch robot in Gazebo GUI")
    print("  - Set new goals in RViz: Toolbar → '2D Goal Pose'")
    print("  - Click and drag to set goal position and orientation")
    print("  - Robot will navigate autonomously using trained policy")
    print("\nPress Ctrl+C to stop.\n")
    
    try:
        while rclpy.ok():
            # Wait for valid state
            state = None
            for _ in range(100):
                executor.spin_once(timeout_sec=0.1)
                state = demo.get_state()
                if state is not None:
                    break
            
            if state is None:
                print("⚠  No sensor data")
                break
            
            # Navigate to current goal
            done = False
            steps = 0
            
            while not done and steps < 500 and rclpy.ok():
                # Get action from trained policy
                action = demo.agent.select_action(state, add_noise=False)
                
                demo.publish_action(action)
                
                for _ in range(5):
                    executor.spin_once(timeout_sec=0.02)
                
                done, reward = demo.check_done()
                state = demo.get_state()
                
                if state is None:
                    break
                
                steps += 1
            
            # Stop and reset world after each episode
            demo.stop()
            import time
            time.sleep(0.5)
            
            # Reset world to clear collision/goal state
            demo.reset(executor)
            time.sleep(1.0)
    
    except (KeyboardInterrupt, ExternalShutdownException):
        print("\n[Stopped] Demo ended.")
    finally:
        demo.stop()
        executor.remove_node(demo)
        demo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main_loop()
