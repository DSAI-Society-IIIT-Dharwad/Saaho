"""
DQN Inference Node — proper implementation
  - Smart turn direction (open space + goal direction)
  - Waypoint navigation for long routes
  - Stuck detection + recovery (back up + turn)
  - Reactive safety layer
  - Both RViz goal tools (Publish Point + 2D Goal Pose)
"""

import os
import math
import time

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist, PoseStamped, PointStamped
from std_srvs.srv import Empty
import torch
import torch.nn as nn

# ── Constants ──────────────────────────────────────────────────
GOAL_RADIUS    = 0.35   # m  — goal reached threshold
WAYPOINT_STEP  = 1.2    # m  — max distance per waypoint sub-goal
SAFETY_SLOW    = 0.30   # m  — start slowing when front obstacle closer than this
SAFETY_HARD    = 0.20   # m  — force a turn when front obstacle closer than this
STUCK_TIME     = 10.0   # s  — declare stuck if robot moved < STUCK_DIST in this window
STUCK_DIST     = 0.05   # m  — minimum movement to NOT be considered stuck
RECOVER_BACK   = 2.0    # s  — how long to back up during recovery
RECOVER_TURN   = 2.0    # s  — how long to turn after backing up
MAX_RECOVERIES = 3      # auto world-reset after this many consecutive failed recoveries


# ── DQN Network (matches trained model architecture) ───────────
class DQN(nn.Module):
    def __init__(self, state_dim, action_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 128), nn.ReLU(),
            nn.Linear(128, 128),       nn.ReLU(),
            nn.Linear(128, action_dim)
        )

    def forward(self, x):
        return self.net(x)


# ── Inference Node ─────────────────────────────────────────────
class DQNInferenceNode(Node):
    def __init__(self):
        super().__init__("dqn_inference")

        # Robot state
        self.scan      = None
        self.robot_x   = 0.0
        self.robot_y   = 0.0
        self.robot_yaw = 0.0

        # Navigation state
        self.active    = False
        self.waypoints = []       # [(x,y), ...]
        self.wp_idx    = 0

        # Stuck detection
        self.stuck_ref_x    = 0.0
        self.stuck_ref_y    = 0.0
        self.stuck_ref_time = time.time()

        # Recovery state machine:  idle | backing | turning
        self.recovery_phase     = "idle"
        self.recovery_start     = 0.0
        self.recovery_turn_sign = 1.0   # +1 = left, -1 = right
        self.recovery_count     = 0     # consecutive recoveries — auto-reset after MAX_RECOVERIES

        # Subscriptions
        self.create_subscription(LaserScan,    "/scan",                  self._scan_cb,       10)
        self.create_subscription(Odometry,     "/odom",                  self._odom_cb,       10)
        self.create_subscription(PoseStamped,  "/move_base_simple/goal", self._pose_goal_cb,  10)
        self.create_subscription(PoseStamped,  "/goal_pose",             self._pose_goal_cb,  10)
        self.create_subscription(PointStamped, "/goal",                  self._point_goal_cb, 10)

        self.cmd_pub      = self.create_publisher(Twist, "/cmd_vel", 10)
        self.reset_client = self.create_client(Empty, "/reset_world")

        # Load model
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.pt")
        self.model = DQN(26, 2)
        self.model.load_state_dict(
            torch.load(model_path, map_location="cpu", weights_only=True)
        )
        self.model.eval()

        self.create_timer(0.1, self._control_loop)
        self.get_logger().info("🚀 DQN ready — click a goal in RViz (Publish Point tool)")

    # ── Sensor callbacks ───────────────────────────────────────
    def _scan_cb(self, msg):
        raw = np.array(msg.ranges, dtype=np.float32)
        self.scan = np.nan_to_num(raw, nan=3.5, posinf=3.5, neginf=0.0)

    def _odom_cb(self, msg):
        self.robot_x   = msg.pose.pose.position.x
        self.robot_y   = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        self.robot_yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        )

    # ── Goal callbacks ─────────────────────────────────────────
    def _pose_goal_cb(self, msg):
        self._set_goal(msg.pose.position.x, msg.pose.position.y)

    def _point_goal_cb(self, msg):
        self._set_goal(msg.point.x, msg.point.y)

    def _set_goal(self, gx, gy):
        dx = gx - self.robot_x
        dy = gy - self.robot_y
        total = math.sqrt(dx * dx + dy * dy)

        # Build waypoint list
        self.waypoints = []
        if total > WAYPOINT_STEP:
            steps = int(math.ceil(total / WAYPOINT_STEP))
            for i in range(1, steps):
                t = i / steps
                self.waypoints.append((
                    self.robot_x + t * dx,
                    self.robot_y + t * dy
                ))
        self.waypoints.append((gx, gy))

        self.wp_idx       = 0
        self.active       = True
        self.recovery_phase = "idle"

        self._reset_stuck_ref()

        n = len(self.waypoints)
        self.get_logger().info(
            f"🎯 Goal: ({gx:.2f}, {gy:.2f})  dist={total:.1f}m  "
            f"{'→ ' + str(n) + ' waypoints' if n > 1 else 'direct'}"
        )

    def _reset_stuck_ref(self):
        self.stuck_ref_x    = self.robot_x
        self.stuck_ref_y    = self.robot_y
        self.stuck_ref_time = time.time()

    # ── Scan sector helper ─────────────────────────────────────
    def _sectors(self):
        """Return (min_front, min_left, min_right) from current scan."""
        n       = len(self.scan)
        front_n = max(1, n // 8)                              # ±45°
        front   = list(range(front_n)) + list(range(n - front_n, n))
        left    = list(range(front_n,     n // 2))
        right   = list(range(n // 2, n - front_n))
        mf = float(min(self.scan[i] for i in front))
        ml = float(min(self.scan[i] for i in left))  if left  else 3.5
        mr = float(min(self.scan[i] for i in right)) if right else 3.5
        return mf, ml, mr

    # ── State vector ───────────────────────────────────────────
    def _state(self, wp_x, wp_y):
        """Build 26-dim state vector (matches training env exactly)."""
        idx  = np.linspace(0, len(self.scan) - 1, 24, dtype=int)
        scan = self.scan[idx] / 3.5

        dist  = math.hypot(wp_x - self.robot_x, wp_y - self.robot_y) / 4.0
        angle = math.atan2(wp_y - self.robot_y, wp_x - self.robot_x) - self.robot_yaw
        angle = math.atan2(math.sin(angle), math.cos(angle)) / math.pi

        return np.append(scan, [dist, angle]).astype(np.float32)

    # ── Control loop (10 Hz) ───────────────────────────────────
    def _control_loop(self):
        if self.scan is None:
            return

        now = time.time()

        # ── Recovery: back up ────────────────────────────────
        if self.recovery_phase == "backing":
            if now - self.recovery_start < RECOVER_BACK:
                t = Twist()
                t.linear.x = -0.10
                self.cmd_pub.publish(t)
            else:
                self.recovery_phase = "turning"
                self.recovery_start = now
            return

        # ── Recovery: turn toward open space ─────────────────
        if self.recovery_phase == "turning":
            if now - self.recovery_start < RECOVER_TURN:
                t = Twist()
                t.angular.z = 0.7 * self.recovery_turn_sign
                self.cmd_pub.publish(t)
            else:
                self.recovery_phase = "idle"
                self._reset_stuck_ref()
                self.get_logger().info("✅ Recovery done — resuming navigation")
            return

        if not self.active:
            return

        # ── Current waypoint ─────────────────────────────────
        wp_x, wp_y = self.waypoints[self.wp_idx]
        is_final   = (self.wp_idx == len(self.waypoints) - 1)
        dx = wp_x - self.robot_x
        dy = wp_y - self.robot_y
        dist_wp = math.sqrt(dx * dx + dy * dy)

        # Waypoint / goal reached
        if dist_wp < GOAL_RADIUS:
            self.cmd_pub.publish(Twist())
            if is_final:
                self.active = False
                self.get_logger().info(
                    f"✅ Goal reached! ({self.robot_x:.2f}, {self.robot_y:.2f})"
                )
            else:
                self.wp_idx += 1
                self.recovery_count = 0
                self._reset_stuck_ref()
                self.get_logger().info(
                    f"  ✓ Waypoint {self.wp_idx}/{len(self.waypoints)} reached"
                )
            return

        # ── Stuck detection ───────────────────────────────────
        if now - self.stuck_ref_time >= STUCK_TIME:
            moved = math.hypot(
                self.robot_x - self.stuck_ref_x,
                self.robot_y - self.stuck_ref_y
            )
            if moved < STUCK_DIST:
                self.recovery_count += 1
                if self.recovery_count >= MAX_RECOVERIES:
                    self.get_logger().info(
                        f"♻️  {MAX_RECOVERIES} recoveries failed — resetting world"
                    )
                    self.active = False
                    self.recovery_count = 0
                    self.cmd_pub.publish(Twist())
                    if self.reset_client.service_is_ready():
                        self.reset_client.call_async(Empty.Request())
                    return
                _, ml, mr = self._sectors()
                self.recovery_turn_sign = 1.0 if ml > mr else -1.0
                self.recovery_phase     = "backing"
                self.recovery_start     = now
                self.cmd_pub.publish(Twist())
                self.get_logger().info(
                    f"🔁 Stuck (moved {moved:.3f}m) — recovery {self.recovery_count}/{MAX_RECOVERIES}"
                )
                return
            self.recovery_count = 0
            self._reset_stuck_ref()

        # ── DQN inference ────────────────────────────────────
        s_t = torch.tensor(self._state(wp_x, wp_y)).unsqueeze(0)
        with torch.no_grad():
            q = self.model(s_t)[0]
        action = int(q.argmax())

        mf, ml, mr = self._sectors()

        # Goal bearing
        goal_angle = math.atan2(dy, dx) - self.robot_yaw
        goal_angle = math.atan2(math.sin(goal_angle), math.cos(goal_angle))

        if action == 0:          # forward
            lin = 0.15
            ang = 0.0
        else:                    # turn — pick smartest direction
            # Open-space side takes priority; fall back to goal bearing
            if abs(ml - mr) > 0.10:
                sign = 1.0 if ml > mr else -1.0
            else:
                sign = 1.0 if goal_angle >= 0 else -1.0
            lin = 0.05
            ang = 0.5 * sign

        # ── Reactive safety overlay ───────────────────────────
        if mf < SAFETY_SLOW and lin > 0:
            scale = max(0.0, (mf - SAFETY_HARD) / (SAFETY_SLOW - SAFETY_HARD))
            lin  *= scale
            if mf < SAFETY_HARD:
                sign = 1.0 if ml > mr else -1.0
                ang  = 1.0 * sign
                lin  = 0.0

        t = Twist()
        t.linear.x  = lin
        t.angular.z = ang
        self.cmd_pub.publish(t)


# ── Entry point ────────────────────────────────────────────────
def main():
    rclpy.init()
    node = DQNInferenceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cmd_pub.publish(Twist())
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
