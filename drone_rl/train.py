"""
train.py — DRL training loop for TurtleBot3 goal navigation.

Usage (inside container, with Gazebo already running):
    source /opt/ros/humble/setup.bash
    cd ~/drone_rl
    python3 train.py
"""

import rclpy
from rclpy.executors import SingleThreadedExecutor, ExternalShutdownException
import time
import os
import random
import signal

from env   import Env
from agent import DQNAgent

# ── Config ─────────────────────────────────────────────────────────────────────
NUM_EPISODES  = 1_000
SAVE_EVERY    = 50        # save model every N episodes
LOG_EVERY     = 10        # print averaged stats every N episodes
WARM_UP_STEPS = 500       # random actions before gradient updates start
SPIN_STEPS    = 5         # executor spins per action step


def main():
    rclpy.init()
    env      = Env(goal_x=1.5, goal_y=1.5)
    executor = SingleThreadedExecutor()
    executor.add_node(env)

    # Warm up executor — wait for /reset_world service
    executor.spin_once(timeout_sec=1.0)

    agent = DQNAgent(state_dim=env.state_dim, action_dim=env.action_dim)

    # ── optionally resume a saved model ───────────────────────────────────────
    if os.path.exists("model.pt"):
        agent.load("model.pt")
        print("Resuming from saved model 🔄")

    total_steps = 0
    ep_rewards  = []

    print(f"\n{'='*55}")
    print(f" TurtleBot3 DQN Training  |  {NUM_EPISODES} episodes")
    print(f"{'='*55}\n")

    try:
        for ep in range(1, NUM_EPISODES + 1):
            if not rclpy.ok():
                break

            # ── reset world, robot teleports back to spawn ─────────────────────
            env.reset_episode(executor)

            ep_reward = 0.0
            done      = False
            losses    = []

            # ── wait for a valid scan after world reset ─────────────────────────
            found_scan = False
            for _ in range(100):
                if not rclpy.ok():
                    break
                executor.spin_once(timeout_sec=0.1)
                if env.get_state() is not None:
                    found_scan = True
                    break
            
            if not found_scan:
                print(f"[Ep {ep:4d}] ⚠  No sensor data — is Gazebo running?")
                time.sleep(1.0)
                continue

            state = env.get_state()

            # ── episode loop ───────────────────────────────────────────────────
            while not done and rclpy.ok():
                # warm-up: pure random actions to fill replay buffer
                if total_steps < WARM_UP_STEPS:
                    action = random.randint(0, env.action_dim - 1)
                else:
                    action = agent.select_action(state)

                # publish velocity, then spin to receive new sensor readings
                env.publish_action(action)
                for _ in range(SPIN_STEPS):
                    if not rclpy.ok():
                        break
                    executor.spin_once(timeout_sec=0.02)

                reward, done = env.get_reward_done()
                next_state   = env.get_state()
                ep_reward   += reward

                if next_state is not None:
                    agent.memory.push(state, action, reward, next_state, done)
                    state = next_state

                loss = agent.train_step()
                if loss is not None:
                    losses.append(loss)

                total_steps += 1

            agent.decay_epsilon()
            ep_rewards.append(ep_reward)

            # ── logging ─────────────────────────────────────────────────────────
            if ep % LOG_EVERY == 0:
                avg_r    = sum(ep_rewards[-LOG_EVERY:]) / LOG_EVERY
                avg_loss = sum(losses) / len(losses) if losses else 0.0
                print(f"[Ep {ep:4d}/{NUM_EPISODES}]  "
                      f"avg_reward={avg_r:+8.2f}  "
                      f"avg_loss={avg_loss:.4f}  "
                      f"eps={agent.epsilon:.3f}  "
                      f"steps={total_steps}")

            if ep % SAVE_EVERY == 0:
                agent.save(f"model_ep{ep}.pt")
                agent.save("model.pt")

    except (KeyboardInterrupt, ExternalShutdownException):
        print("\n[Interrupt] Shutting down...")
    finally:
        # ── final save ─────────────────────────────────────────────────────────────
        agent.save("model_interrupted.pt")
        print("Model saved on shutdown.")
        executor.remove_node(env)
        env.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
