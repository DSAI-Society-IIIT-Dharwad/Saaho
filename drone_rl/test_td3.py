"""
test_td3.py — Test trained TD3 agent for goal navigation.

Runs the trained policy WITHOUT exploration noise to evaluate performance.
"""

import rclpy
from rclpy.executors import SingleThreadedExecutor, ExternalShutdownException
from env import Env
from agent_td3 import TD3Agent
import time

NUM_TEST_EPISODES = 10
MAX_STEPS_PER_EP  = 500


def main():
    rclpy.init()
    env = Env(goal_x=1.5, goal_y=1.5)
    executor = SingleThreadedExecutor()
    executor.add_node(env)
    
    # Warm up
    executor.spin_once(timeout_sec=1.0)
    
    # Load trained model
    agent = TD3Agent(state_dim=env.state_dim, action_dim=env.action_dim)
    agent.load("model_td3.pt")
    
    print(f"\n{'='*60}")
    print(f" Testing Trained TD3 Agent — {NUM_TEST_EPISODES} Episodes")
    print(f"{'='*60}\n")
    
    successes = 0
    collisions = 0
    timeouts = 0
    
    try:
        for ep in range(1, NUM_TEST_EPISODES + 1):
            if not rclpy.ok():
                break
            
            env.reset_episode(executor)
            
            # Wait for valid sensor data
            found_scan = False
            for _ in range(100):
                if not rclpy.ok():
                    break
                executor.spin_once(timeout_sec=0.1)
                if env.get_state() is not None:
                    found_scan = True
                    break
            
            if not found_scan:
                print(f"[Test {ep:2d}] ⚠  No sensor data")
                continue
            
            state = env.get_state()
            done = False
            steps = 0
            ep_reward = 0.0
            
            while not done and steps < MAX_STEPS_PER_EP and rclpy.ok():
                # NO exploration noise — pure exploitation
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
            
            # Categorize result
            if reward > 100:
                result = "🎯 GOAL"
                successes += 1
            elif reward < -100:
                result = "💥 Collision"
                collisions += 1
            else:
                result = "⏱  Timeout"
                timeouts += 1
            
            print(f"[Test {ep:2d}/{NUM_TEST_EPISODES}]  {result:15s}  "
                  f"steps={steps:3d}  reward={ep_reward:+7.1f}")
        
        # Final stats
        print(f"\n{'='*60}")
        print(f" Test Results Summary")
        print(f"{'='*60}")
        print(f"  Success rate:    {successes}/{NUM_TEST_EPISODES} ({100*successes/NUM_TEST_EPISODES:.0f}%)")
        print(f"  Collisions:      {collisions}/{NUM_TEST_EPISODES}")
        print(f"  Timeouts:        {timeouts}/{NUM_TEST_EPISODES}")
        print(f"{'='*60}\n")
        
        if successes >= 8:
            print("✅ EXCELLENT — Agent learned robust goal navigation!")
        elif successes >= 5:
            print("✅ GOOD — Agent can reach goal most of the time")
        else:
            print("⚠️  Needs more training or hyperparameter tuning")
    
    except (KeyboardInterrupt, ExternalShutdownException):
        print("\n[Interrupt] Test stopped.")
    finally:
        executor.remove_node(env)
        env.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
