# TD3 vs DQN — TurtleBot3 Navigation

## What Changed

Your setup is now **TD3-compatible** with **continuous actions** instead of discrete.

### Before (DQN)

- **Action space:** Discrete {0, 1, 2}
  - 0 = forward (0.15 m/s, 0 rad/s)
  - 1 = turn left (0 m/s, 0.5 rad/s)
  - 2 = turn right (0 m/s, -0.5 rad/s)
- **Algorithm:** Deep Q-Network
- **Training file:** `train.py` with `agent.py`

### After (TD3)

- **Action space:** Continuous `[linear_vel, angular_vel]`
  - `linear_vel` ∈ [0.0, 0.22] m/s
  - `angular_vel` ∈ [-2.0, 2.0] rad/s
- **Algorithm:** Twin Delayed Deep Deterministic Policy Gradient
- **Training file:** `train_td3.py` with `agent_td3.py`

---

## File Structure

```
/root/drone_rl/               # Inside container
├── env.py                    # ✅ Updated for continuous actions
├── agent.py                  # DQN agent (old, discrete)
├── agent_td3.py              # ✅ NEW TD3 agent (continuous)
├── train.py                  # DQN training (old)
├── train_td3.py              # ✅ NEW TD3 training
├── model.pt                  # DQN checkpoint
├── model_td3.pt              # TD3 checkpoint (will be created)
└── train_td3.log             # TD3 training output
```

---

## How TD3 Works

### Architecture

**Actor (Policy Network):**
- Input: state (26 dim)
- Output: action (2 dim) in [-1, 1]
- Scaled to actual ranges: [0, 0.22] × [-2.0, 2.0]
- 256 → 256 → tanh activation

**Critic (Q-Network):**
- Input: state (26) + action (2)
- Output: Q-value (1)
- **Twin critics** (2 networks) for stability
- Uses minimum Q-value (clipped double Q-learning)

### Key Features

1. **Continuous actions** — smooth velocity control
2. **Twin critics** — reduces overestimation bias
3. **Delayed policy updates** — actor updates every 2 critic updates
4. **Target policy smoothing** — adds noise to target actions
5. **Exploration noise** — Gaussian noise during training

### Hyperparameters

```python
MEMORY_SIZE = 100_000
BATCH_SIZE = 64
GAMMA = 0.99
LR_ACTOR = 1e-4
LR_CRITIC = 3e-4
TAU = 0.005              # soft update rate
POLICY_DELAY = 2         # actor update frequency
EXPLORATION_NOISE = 0.1  # training noise std
```

---

## Current Status

**Gazebo:** Running (same as before)  
**TD3 Training:** Running with 1000-step warm-up (random actions)  
**Process:** `train_td3.py` logging to `train_td3.log`

### Monitor TD3 Training

```bash
# Live output
docker exec -it ros2_container tail -f /root/drone_rl/train_td3.log

# Check process
docker exec ros2_container ps aux | grep train_td3
```

---

## Expected Behavior

### Warm-up Phase (0–1000 steps)

- Random continuous actions
- Many collisions (normal)
- No gradient updates yet
- Building replay buffer

### Early Training (1000–5000 steps)

- TD3 starts learning
- Exploration noise active
- Collisions still frequent
- Critic loss appears in logs

### Mid Training (5000–20000 steps)

- Smoother navigation
- Actor loss appears (delayed updates)
- Avg reward improves
- Fewer collisions

### Late Training (20000+ steps)

- Goal-reaching behavior emerges
- Continuous turning + forward motion
- Higher rewards
- Stable critic/actor losses

---

## Training Output Format

Every 10 episodes:

```
[Ep   10/1000]  avg_reward= -650.45  critic_loss=0.1234  actor_loss=0.0567  steps=2500
```

- **avg_reward:** Average over last 10 episodes (should increase)
- **critic_loss:** Twin critic MSE loss
- **actor_loss:** Policy gradient loss (only after warm-up)
- **steps:** Total environment steps so far

---

## DQN vs TD3 Comparison

| Feature | DQN (Discrete) | TD3 (Continuous) |
|---------|----------------|------------------|
| **Action space** | {0,1,2} | [linear, angular] |
| **Action type** | Categorical | Real-valued |
| **Exploration** | ε-greedy | Gaussian noise |
| **Networks** | 1 Q-network | 1 Actor + 2 Critics |
| **Stability** | Medium | High (twin critics) |
| **Sample efficiency** | Lower | Higher |
| **Smoothness** | Jerky movements | Smooth control |
| **Best for** | Simple tasks | Continuous control |

### Visual Difference

**DQN behavior:**
```
→ Forward → Stop → Turn left → Stop → Forward → Collision
```

**TD3 behavior:**
```
→ Forward (0.15) + slight turn (-0.3) → smooth arc → goal
```

---

## Commands

### Start TD3 Training (if not running)

```bash
docker exec -it ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 train_td3.py'
```

### Stop TD3 Training

```bash
docker exec ros2_container pkill -f train_td3
```

### Switch Back to DQN (if needed)

```bash
# Stop TD3
docker exec ros2_container pkill -f train_td3

# Revert env.py to discrete actions (or keep a backup)
# Then run:
docker exec -it ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 train.py'
```

---

## Troubleshooting

### "ImportError: No module named agent_td3"

Files weren't copied. Run:

```bash
docker cp drone_rl/agent_td3.py ros2_container:/root/drone_rl/
docker cp drone_rl/train_td3.py ros2_container:/root/drone_rl/
docker cp drone_rl/env.py ros2_container:/root/drone_rl/
```

### Training too slow

- TD3 is compute-heavy (6 networks: actor + 2 critics + 3 targets)
- Warm-up is 1000 steps (vs 500 for DQN)
- Expected: ~2-3 min per 10 episodes early on

### No actor_loss in logs

- Normal during warm-up (first 1000 steps)
- Actor only updates after critic stabilizes
- Will appear after warm-up + delayed policy kicks in

### Actions out of bounds

Already clipped in `env.publish_action()`:
- `linear_vel` → [0.0, 0.22]
- `angular_vel` → [-2.0, 2.0]

---

## Model Checkpoints

- **Auto-save:** Every 50 episodes → `model_td3_ep{N}.pt`
- **Latest:** `model_td3.pt` (overwrites each save)
- **On interrupt:** `model_td3_interrupted.pt`

Resume from checkpoint:

```python
agent.load("model_td3_ep50.pt")
```

---

## Performance Tips

1. **Longer warm-up** for continuous control (1000 steps is good)
2. **Lower learning rates** than DQN (actor 1e-4, critic 3e-4)
3. **Larger replay buffer** (100k vs 50k for DQN)
4. **Patience** — TD3 converges slower but more stable
5. **Reward shaping** — adjust distance/collision penalties if needed

---

## Next Steps

1. Let warm-up complete (1000 steps ~= 5-8 episodes)
2. Monitor critic_loss stabilization
3. Watch for actor_loss to appear (indicates policy learning)
4. Check avg_reward trend over 50-100 episodes
5. Visualize with gzclient to see smooth continuous motion
6. Compare final performance with DQN baseline

---

## Why TD3 is Better Here

- **TurtleBot3 has continuous motors** — TD3 matches hardware
- **Smooth trajectories** — better for collision avoidance
- **More stable** — twin critics prevent Q-value overestimation
- **Sample efficient** — learns faster from experience
- **Real robotics standard** — TD3/SAC are industry standard for continuous control

DQN was good for proof-of-concept, TD3 is production-ready.
