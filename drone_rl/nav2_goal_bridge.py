"""
nav2_goal_bridge.py — Optional NavigateToPose action server for Nav2 *panel* workflows.

In ROS 2 Humble, nav2_rviz_plugins/GoalTool does NOT send goals to an action server
directly; it forwards to the Nav2 RViz *panel*, which then calls NavigateToPose.
Without that full panel stack, the drag tool does nothing useful.

**Recommended:** use rviz_default_plugins/SetGoal (publishes PoseStamped to
`/move_base_simple/goal`) or Publish Point on `/goal` — see `config/rviz_config.rviz`.

This node still helps if you add the Navigation 2 panel and point it at `/navigate_to_pose`.
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from geometry_msgs.msg import PointStamped
from nav2_msgs.action import NavigateToPose
import threading


class Nav2GoalBridge(Node):
    def __init__(self):
        super().__init__("nav2_goal_bridge")

        # Publish forwarded goals to the same topic the demo listens on
        self.goal_pub = self.create_publisher(PointStamped, "/goal", 10)

        # Fake NavigateToPose action server
        self._action_server = ActionServer(
            self,
            NavigateToPose,
            "navigate_to_pose",
            execute_callback=self._execute_cb,
            goal_callback=self._goal_cb,
            cancel_callback=self._cancel_cb,
        )

        self.get_logger().info("✅ Nav2 Goal Bridge ready!")
        self.get_logger().info("   Drag '2D Goal Pose' in RViz → robot will navigate there.")

    def _goal_cb(self, goal_request):
        x = goal_request.pose.pose.position.x
        y = goal_request.pose.pose.position.y
        self.get_logger().info(f"🎯 Nav2 goal received: ({x:.2f}, {y:.2f})")
        return GoalResponse.ACCEPT

    def _cancel_cb(self, goal_handle):
        self.get_logger().info("⚠  Nav2 goal cancelled")
        return CancelResponse.ACCEPT

    def _execute_cb(self, goal_handle: ServerGoalHandle):
        pose = goal_handle.request.pose.pose
        x = pose.position.x
        y = pose.position.y

        # Forward to /goal as PointStamped (what the demo listens to)
        msg = PointStamped()
        msg.header.frame_id = goal_handle.request.pose.header.frame_id or "odom"
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.point.x = x
        msg.point.y = y
        msg.point.z = 0.0
        self.goal_pub.publish(msg)
        self.get_logger().info(f"   ↳ Forwarded to /goal: ({x:.2f}, {y:.2f})")

        # Mark succeeded so RViz doesn't show an error
        goal_handle.succeed()
        result = NavigateToPose.Result()
        return result


def main():
    rclpy.init()
    node = Nav2GoalBridge()

    print("\n" + "="*55)
    print("  Nav2 Goal Bridge  —  RViz drag tool enabled")
    print("="*55)
    print("  Drag '2D Goal Pose' arrow in RViz toolbar")
    print("  Goals forwarded to robot automatically")
    print("  Ctrl+C to stop")
    print("="*55 + "\n")

    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        print("\n[Bridge stopped]")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
