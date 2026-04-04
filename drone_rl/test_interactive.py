"""
test_interactive.py — Test trained TD3 agent with custom goal positions.

Usage:
    python3 test_interactive.py [goal_x] [goal_y]
    
Example:
    python3 test_interactive.py 2.0 -1.0    # Custom goal
    python3 test_interactive.py              # Default (1.5, 1.5)

The robot will navigate to the specified goal using the trained policy.
Watch in Gazebo GUI to see smooth continuous control!
"""

import rclpy
from rclpy.executors import SingleThreadedExecutor, ExternalShutdownException
from env import Env
from agent_td3 import TD3Agent
import sys


def main():
    # Parse goal from command line
    if len(sys.argv) >= 3:
        goal_x = float(sys.argv[1])
        goal_y = float(sys.argv[2])
    else:
        goal_x = 1.5
        goal_y = 1.5
    
    print(f"\n{'='*60}")
    print(f" TD3 Interactive Test — Goal: ({goal_x:.2f}, {goal_y:.2f})")
    print(f"{'='*60}\n")
    
    rclpy.init()
    env = Env(goal_x=goal_x, goal_y=goal_y)
    executor = SingleThreadedExecutor()
    executor.add_node(env)
    
    # Warm up
    executor.spin_once(timeout_sec=1.0)
    
    # Load trained model
    agent = TD3Agent(state_dim=env.state_dim, action_dim=env.action_dim)
    agent.load("model_td3.pt")
    
    print("Trained model loaded. Starting navigation...")
    print("Press Ctrl+C to stop.\n")
    
    episode = 1
    
    try:
        while rclpy.ok():
            print(f"[Episode {episode}] Navigating to ({goal_x:.2f}, {goal_y:.2f})...")
            
            env.reset_episode(executor)
            
            # Wait for sensor data
            found_scan = False
            for _ in range(100):
                if not rclpy.ok():
                    break
                executor.spin_once(timeout_sec=0.1)
                if env.get_state() is not None:
                    found_scan = True
                    break
            
            if not found_scan:
                print("⚠  No sensor data — is Gazebo running?")
                break
            
            state = env.get_state()
            done = False
            steps = 0
            ep_reward = 0.0
            
            while not done and steps < 500 and rclpy.ok():
                # Pure exploitation (no exploration noise)
                action = agent.select_action(state, add_noise=False)
                
                env.publish_action(action)
                for _ in range(5):
                    if not rclpy.ok():
                        break
                    executor.spin_once(timeout_sec=0.02)
                
                reward, done = env.get_reward_done()
                next_state = env.get_state()
                ep_reward += reward
                
                if next_state is not None:
                    state = next_state
                
                steps += 1
            
            # Result
            if reward > 100:
                result = "🎯 GOAL REACHED"
            elif reward < -100:
                result = "💥 Collision"
            else:
                result = "⏱  Timeout"
            
            print(f"  → {result}  |  Steps: {steps}  |  Reward: {ep_reward:+.1f}\n")
            
            episode += 1
            
            # Pause between episodes
            import time
            time.sleep(2)
    
    except (KeyboardInterrupt, ExternalShutdownException):
        print("\n[Stopped] Test ended by user.")
    finally:
        env._stop()
        executor.remove_node(env)
        env.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
