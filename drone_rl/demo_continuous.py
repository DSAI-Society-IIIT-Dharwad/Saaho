"""
demo_continuous.py — Demo that navigates to goals and stays there.

Fixes:
  1. Robot 3D tipping: IMU monitors roll/pitch, resets immediately if robot tips
  2. Spinning timeout: if robot doesn't reach goal in 40s, stops and waits
  3. RViz click goals: accepts PointStamped from PublishPoint tool
"""

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor, ExternalShutdownException
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from sensor_msgs.msg import LaserScan, Imu
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist, PoseStamped, PointStamped
from std_srvs.srv import Empty
import numpy as np
import math
import time
import argparse

from agent_td3 import TD3Agent

N_SCAN_SAMPLES  = 24
GOAL_RADIUS     = 0.35   # metres — within this = goal reached
NAV_TIMEOUT     = 35.0   # seconds — per waypoint timeout
TIP_ANGLE       = 20.0   # degrees — reset if robot tilts more than this
MAX_Z_HEIGHT    = 0.10   # metres — reset if robot gets knocked airborne
WAYPOINT_STEP   = 1.2    # metres — max distance per sub-goal waypoint
STUCK_DIST      = 0.08   # metres — if robot moves less than this in STUCK_TIME, it's stuck
STUCK_TIME      = 8.0    # seconds — how long to wait before declaring stuck

_GOAL_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
    history=HistoryPolicy.KEEP_LAST,
)

# Reactive safety (no reset — just steers/slows away from obstacles)
SAFETY_SLOW_DIST = 0.30  # metres — start scaling down linear velocity
SAFETY_HARD_DIST = 0.20  # metres — force a hard turn toward open space

SPAWN_X = -2.0
SPAWN_Y = -0.5


class ContinuousDemoNode(Node):
    def __init__(self, agent: TD3Agent):
        super().__init__("td3_continuous_demo")
        self.agent = agent

        # State
        self.scan      = None
        self.robot_x   = 0.0
        self.robot_y   = 0.0
        self.robot_z   = 0.0   # height — detects if knocked airborne
        self.robot_yaw = 0.0
        self.roll      = 0.0   # from IMU
        self.pitch     = 0.0   # from IMU
        self.goal_x    = 0.0
        self.goal_y    = 0.0
        self.goal_reached = False
        self.active       = False

        # Subscriptions
        self.create_subscription(LaserScan,    "/scan",                  self._scan_cb,  10)
        self.create_subscription(Odometry,     "/odom",                  self._odom_cb,  10)
        self.create_subscription(Imu,          "/imu",                   self._imu_cb,   10)
        self.create_subscription(PoseStamped,  "/goal_pose",             self._goal_cb,  _GOAL_QOS)
        self.create_subscription(PoseStamped,  "/move_base_simple/goal", self._goal_cb,  _GOAL_QOS)
        self.create_subscription(PointStamped, "/goal",                  self._point_goal_cb, _GOAL_QOS)

        self.vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self._reset_client = self.create_client(Empty, "/reset_world")

        self.get_logger().info("🎯 Demo ready — click a point in RViz to start!")

    # ── callbacks ─────────────────────────────────────────────────────────

    def _scan_cb(self, msg):
        s = np.array(msg.ranges, dtype=np.float32)
        # Match env.py LiDAR preprocessing
        self.scan = np.nan_to_num(s, nan=3.5, posinf=3.5)

    def _odom_cb(self, msg):
        self.robot_x   = msg.pose.pose.position.x
        self.robot_y   = msg.pose.pose.position.y
        self.robot_z   = msg.pose.pose.position.z
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.robot_yaw = math.atan2(siny, cosy)

    def _imu_cb(self, msg):
        """Extract roll and pitch from IMU quaternion."""
        qx = msg.orientation.x
        qy = msg.orientation.y
        qz = msg.orientation.z
        qw = msg.orientation.w
        # Roll (rotation around X)
        sinr = 2.0 * (qw * qx + qy * qz)
        cosr = 1.0 - 2.0 * (qx * qx + qy * qy)
        self.roll  = math.degrees(math.atan2(sinr, cosr))
        # Pitch (rotation around Y)
        sinp = 2.0 * (qw * qy - qz * qx)
        sinp = max(-1.0, min(1.0, sinp))
        self.pitch = math.degrees(math.asin(sinp))

    def _goal_cb(self, msg):
        self.goal_x       = msg.pose.position.x
        self.goal_y       = msg.pose.position.y
        self.goal_reached = False
        self.active       = True
        dx, dy = self.goal_x - self.robot_x, self.goal_y - self.robot_y
        dist = math.sqrt(dx*dx + dy*dy)
        self.get_logger().info(f"🎯 Goal: ({self.goal_x:.2f}, {self.goal_y:.2f})  dist {dist:.2f} m")

    def _point_goal_cb(self, msg: PointStamped):
        """RViz PublishPoint tool sends PointStamped — treat x,y as goal."""
        self.goal_x       = msg.point.x
        self.goal_y       = msg.point.y
        self.goal_reached = False
        self.active       = True
        dx, dy = self.goal_x - self.robot_x, self.goal_y - self.robot_y
        dist = math.sqrt(dx*dx + dy*dy)
        self.get_logger().info(f"🎯 Goal (click): ({self.goal_x:.2f}, {self.goal_y:.2f})  dist {dist:.2f} m")

    # ── helpers ──────────────────────────────────────────────────────────

    def get_state(self):
        """Must match env.py get_state() normalisation exactly (trained policy distribution)."""
        if self.scan is None:
            return None
        idx = np.linspace(0, len(self.scan) - 1, N_SCAN_SAMPLES, dtype=int)
        scan_samples = (self.scan[idx] / 3.5).astype(np.float32)
        dx = self.goal_x - self.robot_x
        dy = self.goal_y - self.robot_y
        goal_dist = math.sqrt(dx * dx + dy * dy) / 4.0
        ang = math.atan2(dy, dx) - self.robot_yaw
        ang = (ang + math.pi) % (2 * math.pi) - math.pi
        goal_angle = ang / math.pi
        return np.append(scan_samples, [np.float32(goal_dist), np.float32(goal_angle)]).astype(np.float32)

    def check_goal(self):
        dx, dy = self.goal_x - self.robot_x, self.goal_y - self.robot_y
        return math.sqrt(dx*dx + dy*dy) < GOAL_RADIUS

    def check_tipped(self):
        """Return True if robot tipped over in 3D or got knocked airborne."""
        tipped   = abs(self.roll) > TIP_ANGLE or abs(self.pitch) > TIP_ANGLE
        airborne = self.robot_z > MAX_Z_HEIGHT
        return tipped or airborne

    def publish_action(self, action):
        """Publish action with a soft reactive safety layer.
        
        Slows down and steers away from obstacles when very close.
        Never resets — just overrides the TD3 output gently.
        """
        lin = float(action[0])
        ang = float(action[1])

        if self.scan is not None:
            n = len(self.scan)
            # With 24 samples at 15°/sample:
            #   index 0        = front (0°)
            #   index 6        = left  (90°)
            #   index 12       = back  (180°)
            #   index 18       = right (270°)
            front_n  = max(1, n // 8)          # ±45° each side → 3 indices
            front_idx  = list(range(front_n)) + list(range(n - front_n, n))
            left_idx   = list(range(front_n,     n // 2))
            right_idx  = list(range(n // 2, n - front_n))

            min_front  = float(min(self.scan[i] for i in front_idx))

            if min_front < SAFETY_SLOW_DIST and lin > 0:
                # Scale linear velocity: full speed at SAFETY_SLOW_DIST, zero at SAFETY_HARD_DIST
                scale = max(0.0, (min_front - SAFETY_HARD_DIST) /
                                 (SAFETY_SLOW_DIST - SAFETY_HARD_DIST))
                lin = lin * scale

                if min_front < SAFETY_HARD_DIST:
                    # Force a turn toward the more open side
                    left_space  = float(min(self.scan[i] for i in left_idx))  if left_idx  else 1.0
                    right_space = float(min(self.scan[i] for i in right_idx)) if right_idx else 1.0
                    if left_space > right_space:
                        ang = max(ang,  1.5)   # turn left
                    else:
                        ang = min(ang, -1.5)   # turn right

        msg = Twist()
        msg.linear.x  = lin
        msg.angular.z = ang
        self.vel_pub.publish(msg)

    def stop(self):
        self.vel_pub.publish(Twist())

    def reset_robot(self, executor):
        """Reset world via Gazebo /reset_world service (puts robot back flat at spawn)."""
        self.stop()
        self.get_logger().info("🔄 Resetting robot...")

        if self._reset_client.service_is_ready():
            fut = self._reset_client.call_async(Empty.Request())
            rclpy.spin_until_future_complete(self, fut, executor=executor, timeout_sec=3.0)
            self.get_logger().info("✅ Reset done")
        else:
            self.get_logger().warn("⚠  /reset_world not ready — skipping")

        # Flush stale sensor data after reset
        self.scan = None
        for _ in range(40):
            executor.spin_once(timeout_sec=0.05)
        time.sleep(1.0)


def main_loop():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="model_td3.pt")
    args = parser.parse_args()

    rclpy.init()

    agent = TD3Agent(state_dim=26, action_dim=2)
    agent.load(args.model)
    print(f"✅ Model loaded: {args.model}")

    demo     = ContinuousDemoNode(agent)
    executor = SingleThreadedExecutor()
    executor.add_node(demo)

    print("\n" + "="*60)
    print("  TD3 Navigation Demo  (2D plane enforced)")
    print("="*60)
    print("  • Click a point in RViz → robot navigates there")
    print("  • Goal reached → robot stays, wait for next click")
    print("  • Collision or tip-over → auto-reset to spawn")
    print(f"  • Spin timeout: {NAV_TIMEOUT}s max per goal")
    print("="*60 + "\n")

    # ── warm up ───────────────────────────────────────────────────────────
    print("⏳ Waiting for sensor data...")
    for _ in range(200):
        executor.spin_once(timeout_sec=0.1)
        if demo.scan is not None:
            break
    if demo.scan is None:
        print("❌ No LiDAR data — is Gazebo running?")
        return

    print(f"✅ Sensors ready. Nearest obstacle: {float(np.min(demo.scan)):.2f} m")
    print("🎯 Click a point in RViz (Publish Point tool) to start.\n")

    # ── main loop ─────────────────────────────────────────────────────────
    try:
        while rclpy.ok():

            # Wait for a new user goal
            while not demo.active and rclpy.ok():
                executor.spin_once(timeout_sec=0.1)

            state = demo.get_state()
            if state is None:
                executor.spin_once(timeout_sec=0.1)
                continue

            # ── Build waypoints ──────────────────────────────────────────
            final_x, final_y = demo.goal_x, demo.goal_y
            dx = final_x - demo.robot_x
            dy = final_y - demo.robot_y
            total_dist = math.sqrt(dx*dx + dy*dy)

            # Divide into WAYPOINT_STEP-sized steps
            waypoints = []
            if total_dist > WAYPOINT_STEP:
                steps = int(math.ceil(total_dist / WAYPOINT_STEP))
                for i in range(1, steps):
                    t = i / steps
                    waypoints.append((
                        demo.robot_x + t * dx,
                        demo.robot_y + t * dy
                    ))
            waypoints.append((final_x, final_y))   # always end at the real goal

            n = len(waypoints)
            if n > 1:
                print(f"📍 Long route ({total_dist:.1f}m) → split into {n} waypoints")

            # ── Navigate each waypoint in sequence ───────────────────────
            reset_needed = False
            for wp_idx, (wp_x, wp_y) in enumerate(waypoints):

                if not rclpy.ok() or not demo.active:
                    break

                # Point demo at this waypoint
                demo.goal_x, demo.goal_y = wp_x, wp_y
                demo.goal_reached = False

                is_final = (wp_idx == len(waypoints) - 1)
                label = "🏁 final goal" if is_final else f"📍 waypoint {wp_idx+1}/{n}"
                print(f"▶  {label}: ({wp_x:.2f}, {wp_y:.2f})")

                nav_start        = time.time()
                stuck_check_x    = demo.robot_x
                stuck_check_y    = demo.robot_y
                stuck_check_time = time.time()

                while demo.active and rclpy.ok():
                    state = demo.get_state()
                    if state is None:
                        break

                    action = demo.agent.select_action(state, add_noise=False)
                    demo.publish_action(action)

                    for _ in range(5):
                        executor.spin_once(timeout_sec=0.02)

                    # ── Waypoint / goal reached ──────────────────────────
                    if demo.check_goal():
                        demo.stop()
                        if is_final:
                            demo.active       = False
                            demo.goal_reached = True
                            print(f"\n✅ Goal reached! Robot at ({demo.robot_x:.2f}, {demo.robot_y:.2f})")
                            print("   Set a new goal to continue.\n")
                        else:
                            print(f"   ✓ Waypoint {wp_idx+1} reached")
                        break

                    # ── Tipped / airborne ────────────────────────────────
                    if demo.check_tipped():
                        demo.stop()
                        demo.active = False
                        print(f"\n⚠️  Tipped over! roll={demo.roll:.1f}°  pitch={demo.pitch:.1f}°")
                        reset_needed = True
                        break

                    # ── Stuck detection (hasn't moved in STUCK_TIME s) ───
                    now = time.time()
                    if now - stuck_check_time >= STUCK_TIME:
                        moved = math.sqrt(
                            (demo.robot_x - stuck_check_x)**2 +
                            (demo.robot_y - stuck_check_y)**2
                        )
                        if moved < STUCK_DIST:
                            demo.stop()
                            demo.active = False
                            print(f"\n🔁 Robot stuck (moved only {moved:.3f}m in {STUCK_TIME}s) — resetting.\n")
                            reset_needed = True
                            break
                        # Reset stuck reference point
                        stuck_check_x    = demo.robot_x
                        stuck_check_y    = demo.robot_y
                        stuck_check_time = now

                    # ── Per-waypoint timeout ─────────────────────────────
                    if now - nav_start > NAV_TIMEOUT:
                        demo.stop()
                        demo.active = False
                        print(f"\n⏱  Timeout — set a new goal.\n")
                        break

                if reset_needed:
                    break

            if reset_needed:
                demo.reset_robot(executor)
                print("🎯 Set a new goal to continue.\n")

    except (KeyboardInterrupt, ExternalShutdownException):
        print("\n[Stopped]")
    finally:
        demo.stop()
        executor.remove_node(demo)
        demo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main_loop()
