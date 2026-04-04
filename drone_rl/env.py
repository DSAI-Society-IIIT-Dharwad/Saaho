"""
env.py — ROS2 Gym-like environment wrapping TurtleBot3 for DRL.

State  : 24 down-sampled LiDAR readings + distance-to-goal + heading error
         → vector of shape (26,)
Actions: Continuous [linear_vel, angular_vel]
         linear_vel ∈ [0.0, 0.22] m/s
         angular_vel ∈ [-2.0, 2.0] rad/s

NOTE: This node does NOT call rclpy.spin*() internally.
      All spinning is owned by the SingleThreadedExecutor in train.py.
"""

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from std_srvs.srv import Empty
import numpy as np
import math
import time

# ── Constants ─────────────────────────────────────────────────────────────────
N_SCAN_SAMPLES    = 24       # sampled LiDAR beams
COLLISION_DIST    = 0.15     # metres — episode ends on collision
GOAL_RADIUS       = 0.30     # metres — episode ends on goal reached
MAX_EPISODE_STEPS = 500


class Env(Node):
    """TurtleBot3 environment node with Gazebo world reset support."""

    def __init__(self, goal_x: float = 1.5, goal_y: float = 1.5):
        super().__init__("drl_env")

        # ── internal state ────────────────────────────────────────────────────
        self.scan: np.ndarray | None = None
        self.robot_x   = 0.0
        self.robot_y   = 0.0
        self.robot_yaw = 0.0
        self.goal_x    = goal_x
        self.goal_y    = goal_y
        self.ep_step   = 0

        # ── ROS2 comms ─────────────────────────────────────────────────────────
        self.create_subscription(LaserScan, "/scan", self._scan_cb, 10)
        self.create_subscription(Odometry,  "/odom", self._odom_cb, 10)
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)

        # Gazebo world-reset service (teleports robot back to spawn)
        self._reset_client = self.create_client(Empty, "/reset_world")
        self.get_logger().info("Env node ready ✅")

    # ── ROS callbacks ─────────────────────────────────────────────────────────
    def _scan_cb(self, msg: LaserScan):
        raw = np.array(msg.ranges, dtype=np.float32)
        self.scan = np.nan_to_num(raw, nan=3.5, posinf=3.5)

    def _odom_cb(self, msg: Odometry):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.robot_yaw = math.atan2(siny, cosy)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _dist_to_goal(self) -> float:
        return math.hypot(self.goal_x - self.robot_x,
                          self.goal_y - self.robot_y)

    def _angle_to_goal(self) -> float:
        """Heading error normalised to [-π, π]."""
        angle = (math.atan2(self.goal_y - self.robot_y,
                            self.goal_x - self.robot_x)
                 - self.robot_yaw)
        return (angle + math.pi) % (2 * math.pi) - math.pi

    def _stop(self):
        self.cmd_pub.publish(Twist())

    # ── public API (no internal spin — caller owns executor) ────────────────
    @property
    def state_dim(self) -> int:
        return N_SCAN_SAMPLES + 2   # scan + dist + angle

    @property
    def action_dim(self) -> int:
        return 2  # [linear_vel, angular_vel]

    def get_state(self) -> np.ndarray | None:
        """Return normalised state vector, or None if sensors not ready."""
        if self.scan is None:
            return None
        idx   = np.linspace(0, len(self.scan) - 1, N_SCAN_SAMPLES, dtype=int)
        scan  = (self.scan[idx] / 3.5).astype(np.float32)
        dist  = np.float32(self._dist_to_goal() / 4.0)
        angle = np.float32(self._angle_to_goal() / math.pi)
        return np.append(scan, [dist, angle])

    def publish_action(self, action: np.ndarray):
        """
        Publish velocity command from continuous action.
        action: [linear_vel, angular_vel] (already scaled to real ranges)
        Does NOT spin — caller must spin after.
        """
        twist = Twist()
        twist.linear.x  = float(np.clip(action[0], 0.0, 0.22))
        twist.angular.z = float(np.clip(action[1], -2.0, 2.0))
        self.cmd_pub.publish(twist)
        self.ep_step += 1

    def get_reward_done(self) -> tuple:
        """Compute reward and done flag from current sensor readings."""
        if self.scan is None:
            return 0.0, False
        min_dist = float(np.min(self.scan))
        dist_g   = self._dist_to_goal()

        if min_dist < COLLISION_DIST:
            self.get_logger().warn("💥 Collision!")
            return -200.0, True
        if dist_g < GOAL_RADIUS:
            self.get_logger().info("🎯 Goal reached!")
            return 200.0, True
        if self.ep_step >= MAX_EPISODE_STEPS:
            return -10.0, True

        r_goal = -0.5 * dist_g
        r_safe = -1.0 if min_dist < 0.30 else 0.0
        return r_goal + r_safe, False

    def reset_episode(self, executor: SingleThreadedExecutor):
        """
        Reset Gazebo world, stop robot, clear stale data.
        Requires the caller's executor to spin the reset future.
        """
        self.ep_step = 0
        self.scan    = None    # discard stale scan
        self._stop()

        if self._reset_client.service_is_ready():
            future = self._reset_client.call_async(Empty.Request())
            rclpy.spin_until_future_complete(self, future, executor=executor,
                                             timeout_sec=3.0)
        else:
            self.get_logger().warn("/reset_world not ready — skipping reset")

        # Flush post-reset messages
        for _ in range(20):
            executor.spin_once(timeout_sec=0.05)
        time.sleep(0.3)
