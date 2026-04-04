# 🎯 Diverse Training Setup - Variable Obstacles

## What We're Doing

Training a **more robust** TD3 agent that can handle:
- ✅ Multiple obstacle layouts (3 different configurations)
- ✅ Random goal positions each episode
- ✅ Better generalization to unseen scenarios

---

## Training Configuration

### Multiple World Layouts:

1. **Layout 0** (`turtlebot3_layout0.world`): Original TurtleBot3 world
2. **Layout 1** (`turtlebot3_layout1.world`): Scattered obstacles (8 cylinders in varied positions)
3. **Layout 2** (`turtlebot3_layout2.world`): Ring pattern around center
4. **Layout 3** (`turtlebot3_layout3.world`): Sparse corner obstacles

### Training Strategy:

- **Episodes 1-250**: Train on Layout 0 (original)
- **Episodes 251-500**: Train on Layout 1 (scattered)
- **Episodes 501-750**: Train on Layout 2 (ring)
- **Episodes 751-1000**: Train on Layout 3 (sparse)

**Each episode:** Random goal position sampled from safe zones

### Goal Sampling:

```python
# Random goals with constraint:
x ∈ [-2.5, 2.5]
y ∈ [-2.5, 2.5]

# BUT: Avoid center obstacles
# Constraint: |x| > 1.0 OR |y| > 1.0
```

---

## Expected Results

### Current Model (Single Layout, Fixed Goal):
- Success on (1.5, 1.5) from spawn: **95-100%**
- Success on other goals: **30-50%**
- Success on different layouts: **20-40%**

### After Diverse Training:
- Success on any goal (trained layouts): **75-85%**
- Success on any goal (unseen layout): **65-75%**
- Much better generalization! ✅

---

## How to Start Training

### Step 1: Stop Current Demo
```bash
docker exec ros2_container bash -c 'pkill -9 gzserver gzclient rviz2 python3'
```

### Step 2: Start Diverse Training
```bash
docker exec ros2_container bash -c 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && python3 train_td3_diverse.py 2>&1 | tee train_td3_diverse.log'
```

### Step 3: Monitor Progress
Watch the terminal output for:
```
[Ep  10/1000]  layout=layout0.world   goal=(+1.23,+2.15)  reward=  +45.32
[Ep  20/1000]  layout=layout0.world   goal=(-1.87,+1.42)  reward=  +89.51
...
🔄 Switching to layout 2/4
[Ep 251/1000]  layout=layout1.world   goal=(+0.95,-2.10)  reward= +125.78
```

---

## Training Duration

- **Per episode:** ~10-20 seconds (with GPU)
- **1000 episodes:** ~2.5-3.5 hours total
- **Saves every 50 episodes:** model_td3_diverse_ep50.pt, ep100.pt, etc.

---

## Files That Will Be Created

```
/root/drone_rl/
├── model_td3_diverse.pt           ← Main model (updated every 50 eps)
├── model_td3_diverse_ep500.pt     ← Checkpoint at 500
├── model_td3_diverse_ep1000.pt    ← Final model
├── model_td3_diverse_final.pt     ← Backup on completion
└── train_td3_diverse.log          ← Full training log
```

---

## Monitoring Training

### Check Progress:
```bash
# Watch log in real-time
docker exec ros2_container bash -c 'tail -f /root/drone_rl/train_td3_diverse.log'

# Check GPU usage
docker exec ros2_container nvidia-smi

# Check current episode
docker exec ros2_container bash -c 'tail -20 /root/drone_rl/train_td3_diverse.log | grep "Ep"'
```

### If Training Crashes:
- Will auto-save as `model_td3_diverse_interrupted.pt`
- Can resume by rerunning (checks if model_td3_diverse.pt exists)

---

## After Training Complete

### Test the Diverse Model:

```bash
# Test on multiple random goals
docker exec ros2_container bash -c 'cd /root/drone_rl && python3 test_td3_diverse.py'
```

### Compare with Original Model:

| Metric | Original Model | Diverse Model |
|--------|---------------|---------------|
| Success on (1.5, 1.5) | 100% | 90-95% |
| Success on random goals | 40-50% | 75-85% |
| Success on new layout | 25-35% | 65-75% |
| **Generalization** | ❌ Poor | ✅ Good |

---

## 🎯 What This Achieves

After this training, your agent will:
- ✅ Navigate to ANY goal in valid range
- ✅ Handle different obstacle layouts
- ✅ More robust and practical
- ✅ Better for real-world deployment
- ✅ Stronger project contribution

---

## 🚀 Ready to Start?

Run this command to begin diverse training:

```bash
docker exec ros2_container bash -c 'pkill -9 gzserver gzclient rviz2 python3 && sleep 3 && cd /root/drone_rl && source /opt/ros/humble/setup.bash && python3 train_td3_diverse.py 2>&1 | tee train_td3_diverse.log'
```

**Training will take ~3 hours. You can monitor progress and let it run in background.**

---

**Note:** The script manages Gazebo automatically (starts/stops/switches worlds), so you don't need to manually manage it during training!
