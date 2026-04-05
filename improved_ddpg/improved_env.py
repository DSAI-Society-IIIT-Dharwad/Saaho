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
N_SCAN_SAMPLES    = 180      # sampled LiDAR beams
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
        self.prev_dist = 0.0
        self.stuck_steps = 0
        self.prev_action = np.zeros(2)
        self.repetitive_count = 0

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
        # Safety Check 1: Data Integrity (Prevent NaN/Inf actions from crashing physics)
        if np.any(np.isnan(action)) or np.any(np.isinf(action)):
            self.get_logger().error("⚠️ SAFETY CHECK FAILED: NaN or Inf detected in action! Forcing stop.")
            action = np.zeros(2)

        # Track repetition of exact or highly similar actions to penalize repetitive loops
        if np.allclose(self.prev_action, action, atol=1e-2):
            self.repetitive_count += 1
        else:
            self.repetitive_count = 0
        self.prev_action = action.copy()

        # Dynamic Safety Governor & Emergency Override
        safe_top_speed = 0.5
        override_angular = None

        if self.scan is not None:
            # Check the central rays + edge rays for forward obstacles. ±18 degrees = 9 rays each side (180 total)
            front_scan_min = float(np.min(np.concatenate((self.scan[:9], self.scan[-9:]))))
            overall_scan_min = float(np.min(self.scan))

            # Safety Check 2: Imminent Collision Shield (Override RL Agent entirely)
            if front_scan_min < 0.20:
                self.get_logger().warn(f"🛡️ SAFETY SHIELD ACTIVATED: Frontal obstacle at {front_scan_min:.2f}m. Overriding network!")
                safe_top_speed = 0.0  # Force brake
                override_angular = 2.84  # Force sharp turn to escape crash
            # Safety Check 3: Progressive Dynamic Braking (Slow down proportional to proximity)
            elif front_scan_min < 0.50:
                safe_top_speed = max(0.05, 0.5 * ((front_scan_min - 0.20) / 0.3))

            # Safety Check 4: Blind Spot Proximity (Limit top speed if ANY obstacle is intimately close on sides/rear)
            if overall_scan_min < 0.22 and override_angular is None:
                safe_top_speed = min(safe_top_speed, 0.15)

        twist = Twist()
        twist.linear.x  = float(np.clip(action[0], 0.0, safe_top_speed))
        twist.angular.z = float(np.clip(action[1], -2.84, 2.84)) if override_angular is None else override_angular
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

        r_progress = (self.prev_dist - dist_g) * 200.0
        
        # Penalize if agent is stuck
        if abs(r_progress) < 0.1:
            self.stuck_steps += 1
        else:
            self.stuck_steps = 0
            
        r_stuck = -5.0 if self.stuck_steps > 15 else 0.0
        
        # Repetition penalty calculation
        r_repeat = -2.0 if self.repetitive_count > 5 else 0.0

        # Update distance
        self.prev_dist = dist_g

        # Smooth safety penalty: grows sharply as the bot approaches obstacles closer than 0.45m
        r_safe = 0.0
        if min_dist < 0.45:
            r_safe = -5.0 * (0.45 - min_dist)  # the closer it gets, the bigger the minus points
            
        # Orient to goal: gently penalizes looking away from the goal to keep it moving straight towards it
        r_heading = -0.5 * abs(self._angle_to_goal())

        # Pure rotation penalty: aggressively penalize turning in place or continuous rotating paths
        r_spin = 0.0
        # Penalize turning without forward progress
        if self.prev_action[0] < 0.1 and abs(self.prev_action[1]) > 0.2:
            r_spin -= 15.0
        # Generally penalize all angular motion to discourage rotating/curved paths
        r_spin -= 5.0 * abs(self.prev_action[1])

        r_time = -0.5  # slight time penalty to encourage speed

        return r_progress + r_safe + r_time + r_stuck + r_repeat + r_heading + r_spin, False
        
    def reset_episode(self, executor: SingleThreadedExecutor):
        """
        Reset Gazebo world, stop robot, clear stale data.
        Requires the caller's executor to spin the reset future.
        """
        import random
        # Pick a new random reachable goal coordinate in turtlebot3_world
        valid_goals = [
            # Inner gaps between pillars
            (0.5, 0.5), (-0.5, 0.5), (0.5, -0.5), (-0.5, -0.5),
            # Outer gaps along X axes
            (1.5, 0.5), (1.5, -0.5), (-1.5, 0.5), (-1.5, -0.5),
            # Outer gaps along Y axes
            (0.5, 1.5), (-0.5, 1.5), (0.5, -1.5), (-0.5, -1.5),
            # Corner regions
            (1.5, 1.5), (-1.5, 1.5), (1.5, -1.5), (-1.5, -1.5),
            # Outer mid-edges
            (0.0, 1.5), (0.0, -1.5), (1.5, 0.0), (-1.5, 0.0)
        ]
        self.goal_x, self.goal_y = random.choice(valid_goals)
        self.get_logger().info(f"📍 New randomized goal set to: ({self.goal_x}, {self.goal_y})")

        # If the goal is dynamically chosen on the 1.5m outer extremes, flag it as highly dangerous (near walls)
        if abs(self.goal_x) >= 1.5 or abs(self.goal_y) >= 1.5:
            self.get_logger().warn(f"⚠️ DANGEROUS ZONE: The goal ({self.goal_x}, {self.goal_y}) is placed critically close to the wall boundary!")

        self.ep_step = 0
        self.scan    = None    # discard stale scan
        self.prev_action = np.zeros(2)
        self.repetitive_count = 0
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
        self.prev_dist = self._dist_to_goal()
        self.stuck_steps = 0
