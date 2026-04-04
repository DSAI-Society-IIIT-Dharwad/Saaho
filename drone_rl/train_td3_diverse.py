"""
train_td3_diverse.py — TD3 training with multiple world layouts and diverse goals.

Features:
- Rotates through 3 different obstacle layouts
- Random goal positions each episode
- Better generalization for variable environments

Usage (inside container, no Gazebo needed - script manages it):
    source /opt/ros/humble/setup.bash
    cd ~/drone_rl
    python3 train_td3_diverse.py
"""

import rclpy
from rclpy.executors import SingleThreadedExecutor, ExternalShutdownException
import time
import os
import signal
import subprocess
import numpy as np

from env import Env
from agent_td3 import TD3Agent

# ── Config ─────────────────────────────────────────────────────────────────────
NUM_EPISODES  = 1_000
SAVE_EVERY    = 50
LOG_EVERY     = 10
WARM_UP_STEPS = 1_000
SPIN_STEPS    = 5

# Multiple world layouts
WORLD_LAYOUTS = [
    "/root/custom_worlds/turtlebot3_layout0.world",  # Original
    "/root/custom_worlds/turtlebot3_layout1.world",  # Scattered
    "/root/custom_worlds/turtlebot3_layout2.world",  # Ring pattern
    "/root/custom_worlds/turtlebot3_layout3.world",  # Sparse corners
]

# Gazebo process
gazebo_proc = None


def sample_random_goal():
    """Sample safe goal positions avoiding center obstacles."""
    while True:
        x = np.random.uniform(-2.5, 2.5)
        y = np.random.uniform(-2.5, 2.5)
        # Avoid center obstacles (keep at least one coordinate away from center)
        if abs(x) > 1.0 or abs(y) > 1.0:
            return float(x), float(y)


def start_gazebo(world_file):
    """Start Gazebo with specified world file."""
    global gazebo_proc
    
    # Stop existing Gazebo
    subprocess.run(['pkill', '-9', 'gzserver'], check=False, 
                   stderr=subprocess.DEVNULL)
    subprocess.run(['pkill', '-9', 'gzclient'], check=False,
                   stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    # Start new Gazebo with selected world
    env_vars = os.environ.copy()
    env_vars['TURTLEBOT3_MODEL'] = 'burger'
    env_vars['LIBGL_ALWAYS_SOFTWARE'] = '1'
    
    cmd = [
        'bash', '-c',
        f'source /opt/ros/humble/setup.bash && '
        f'gzserver {world_file} '
        f'-s libgazebo_ros_init.so '
        f'-s libgazebo_ros_factory.so '
        f'-s libgazebo_ros_force_system.so'
    ]
    
    gazebo_proc = subprocess.Popen(
        cmd,
        env=env_vars,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    print(f"  Started Gazebo with {os.path.basename(world_file)}")
    time.sleep(12)  # Wait for Gazebo to initialize
    
    # Spawn robot
    spawn_cmd = [
        'bash', '-c',
        f'source /opt/ros/humble/setup.bash && '
        f'ros2 run gazebo_ros spawn_entity.py '
        f'-entity burger '
        f'-file /opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf '
        f'-x -2.0 -y -0.5 -z 0.01'
    ]
    
    try:
        subprocess.run(spawn_cmd, env=env_vars, timeout=20,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        print("  ⚠️  Spawn timeout (robot may already exist)")
    time.sleep(3)


def stop_gazebo():
    """Stop Gazebo cleanly."""
    global gazebo_proc
    if gazebo_proc:
        gazebo_proc.terminate()
        gazebo_proc.wait(timeout=5)
    subprocess.run(['pkill', '-9', 'gzserver'], check=False)
    subprocess.run(['pkill', '-9', 'gzclient'], check=False)


def main():
    # Initialize ROS once (Gazebo started/stopped per layout)
    rclpy.init()
    
    # Start with first world
    print("\n" + "="*70)
    print(" TD3 Training with Multiple Layouts & Diverse Goals")
    print("="*70)
    print(f"\nWorld layouts: {len(WORLD_LAYOUTS)}")
    print(f"Episodes: {NUM_EPISODES}")
    print(f"Goal strategy: Random per episode\n")
    
    current_world_idx = 0
    start_gazebo(WORLD_LAYOUTS[current_world_idx])
    
    # Create environment and agent
    goal_x, goal_y = sample_random_goal()
    env = Env(goal_x=goal_x, goal_y=goal_y)
    executor = SingleThreadedExecutor()
    executor.add_node(env)
    executor.spin_once(timeout_sec=1.0)
    
    agent = TD3Agent(state_dim=env.state_dim, action_dim=env.action_dim)
    
    # Resume if exists
    if os.path.exists("model_td3_diverse.pt"):
        agent.load("model_td3_diverse.pt")
        print("Resuming from saved model_td3_diverse.pt 🔄\n")
    
    total_steps = 0
    ep_rewards = []
    layout_switch_interval = NUM_EPISODES // len(WORLD_LAYOUTS)
    
    try:
        for ep in range(1, NUM_EPISODES + 1):
            if not rclpy.ok():
                break
            
            # Switch world layout periodically
            expected_world_idx = (ep - 1) // layout_switch_interval
            if expected_world_idx >= len(WORLD_LAYOUTS):
                expected_world_idx = len(WORLD_LAYOUTS) - 1
            
            if expected_world_idx != current_world_idx:
                print(f"\n🔄 Switching to layout {expected_world_idx + 1}/{len(WORLD_LAYOUTS)}")
                stop_gazebo()
                time.sleep(3)
                start_gazebo(WORLD_LAYOUTS[expected_world_idx])
                current_world_idx = expected_world_idx
                # Recreate environment after Gazebo restart
                executor.remove_node(env)
                env.destroy_node()
                goal_x, goal_y = sample_random_goal()
                env = Env(goal_x=goal_x, goal_y=goal_y)
                executor.add_node(env)
                executor.spin_once(timeout_sec=1.0)
            
            # Sample new random goal for this episode
            goal_x, goal_y = sample_random_goal()
            env.goal_x = goal_x
            env.goal_y = goal_y
            
            # Reset episode
            env.reset_episode(executor)
            
            ep_reward = 0.0
            done = False
            critic_losses = []
            actor_losses = []
            
            # Wait for valid scan
            found_scan = False
            for _ in range(100):
                if not rclpy.ok():
                    break
                executor.spin_once(timeout_sec=0.1)
                if env.get_state() is not None:
                    found_scan = True
                    break
            
            if not found_scan:
                print(f"[Ep {ep:4d}] ⚠  No sensor data")
                time.sleep(1.0)
                continue
            
            state = env.get_state()
            
            # Episode loop
            while not done and rclpy.ok():
                # Warm-up: random actions
                if total_steps < WARM_UP_STEPS:
                    action = np.array([
                        np.random.uniform(0.0, 0.22),
                        np.random.uniform(-2.0, 2.0),
                    ], dtype=np.float32)
                else:
                    action = agent.select_action(state, add_noise=True)
                
                env.publish_action(action)
                for _ in range(SPIN_STEPS):
                    if not rclpy.ok():
                        break
                    executor.spin_once(timeout_sec=0.02)
                
                reward, done = env.get_reward_done()
                next_state = env.get_state()
                ep_reward += reward
                
                if next_state is not None:
                    agent.memory.push(state, action, reward, next_state, done)
                    state = next_state
                
                # Train
                if total_steps >= WARM_UP_STEPS:
                    losses = agent.train_step()
                    if losses is not None:
                        critic_losses.append(losses["critic_loss"])
                        if "actor_loss" in losses:
                            actor_losses.append(losses["actor_loss"])
                
                total_steps += 1
            
            ep_rewards.append(ep_reward)
            
            # Logging
            if ep % LOG_EVERY == 0:
                avg_r = sum(ep_rewards[-LOG_EVERY:]) / LOG_EVERY
                avg_c = sum(critic_losses) / len(critic_losses) if critic_losses else 0.0
                avg_a = sum(actor_losses) / len(actor_losses) if actor_losses else 0.0
                layout_name = os.path.basename(WORLD_LAYOUTS[current_world_idx])
                print(f"[Ep {ep:4d}/{NUM_EPISODES}]  "
                      f"layout={layout_name[:15]:15s}  "
                      f"goal=({goal_x:+5.2f},{goal_y:+5.2f})  "
                      f"reward={avg_r:+8.2f}  "
                      f"c_loss={avg_c:.4f}  a_loss={avg_a:.4f}")
            
            # Save periodically
            if ep % SAVE_EVERY == 0:
                agent.save(f"model_td3_diverse_ep{ep}.pt")
                agent.save("model_td3_diverse.pt")
                print(f"  💾 Saved model_td3_diverse.pt (episode {ep})")
    
    except (KeyboardInterrupt, ExternalShutdownException):
        print("\n[Interrupt] Shutting down...")
    finally:
        agent.save("model_td3_diverse_final.pt")
        print("\n✅ Final model saved: model_td3_diverse_final.pt")
        stop_gazebo()
        executor.remove_node(env)
        env.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
