# TurtleBot3 RL Training — Running Setup

## Current Status

**Container:** `ros2_container` (running)  
**Gazebo:** Running with TurtleBot3 burger model spawned  
**Training:** `train.py` running and resuming from `model.pt`  
**Goal:** Navigate to (1.5, 1.5) with collision avoidance

---

## Active Terminal Processes

| Process | PID (in container) | Status |
|---------|-------------------|--------|
| Gazebo server | ~1068 | Running foreground |
| Gazebo client (GUI) | Not started | Start manually if GUI needed |
| Training | ~1308 | Running, logging to `/root/drone_rl/train.log` |

---

## Monitor Training

```bash
# Live training output
docker exec -it ros2_container tail -f /root/drone_rl/train.log

# Check process status
docker exec ros2_container ps aux | grep -E "train|gzserver"

# View ROS topics
docker exec ros2_container bash -lc 'source /opt/ros/humble/setup.bash && ros2 topic list'

# Test laser scan data
docker exec ros2_container bash -lc 'source /opt/ros/humble/setup.bash && ros2 topic echo /scan --once | head -20'
```

---

## Start Gazebo GUI (Optional)

From **host** terminal:

```bash
# First time per session
./scripts/host-allow-docker-x11.sh
export DISPLAY=:0

# Then start gzclient
docker exec -it -e DISPLAY=$DISPLAY ros2_container bash -lc 'source /opt/ros/humble/setup.bash && gzclient'
```

---

## Start RViz (Optional)

```bash
docker exec -it -e DISPLAY=$DISPLAY ros2_container bash -lc 'source /opt/ros/humble/setup.bash && rviz2'
```

Configure:
- Fixed Frame → `odom`
- Add → LaserScan → Topic `/scan`

---

## Stop Training

```bash
docker exec ros2_container pkill -f "python3.*train.py"
```

Model auto-saves every 50 episodes to `/root/drone_rl/model_ep{N}.pt` and on interrupt to `model_interrupted.pt`.

---

## Clean Restart (Kill Everything + Relaunch)

```bash
# Copy script into container if not already there
docker cp scripts/container/clean-start-gazebo.sh ros2_container:/tmp/

# Run clean startup (kills processes, relaunches Gazebo, verifies robot spawn)
docker exec ros2_container bash /tmp/clean-start-gazebo.sh
```

Then in another terminal:

```bash
docker exec -it ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 train.py'
```

---

## Training Config

- **Episodes:** 1000
- **Warm-up steps:** 500 (random actions before learning)
- **Log every:** 10 episodes
- **Save every:** 50 episodes
- **State:** 26-dim (24 LiDAR samples + distance to goal + heading error)
- **Actions:** 3 (forward, turn left, turn right)
- **Algorithm:** DQN with epsilon-greedy exploration

---

## Expected Behavior

Early episodes (1–50): Many collisions, negative rewards (~-800), high epsilon (>0.9)  
Mid episodes (50–200): Fewer collisions, improving avg reward, epsilon decays  
Later episodes (200+): Goal reaching behavior emerges, positive rewards possible

Training is **working correctly** if you see:
- Collision warnings in the log
- Episode summaries every 10 episodes with avg_reward, avg_loss, eps, steps
- Model checkpoints saved every 50 episodes

---

## Files Structure

```
/root/drone_rl/               # Inside container
├── train.py                  # Training loop
├── env.py                    # ROS2 Gym-like environment
├── agent.py                  # DQN agent + replay buffer
├── model.pt                  # Latest model checkpoint
├── model_ep50.pt             # Saved at episode 50
├── model_interrupted.pt      # Saved on Ctrl+C
└── train.log                 # Training output log
```

On host: `/home/hithx/Documents/H2F/h2f_implementation/drone_rl/` (not mounted in current container)

---

## Troubleshooting

**No `/cmd_vel` topic:**
```bash
docker exec ros2_container bash -lc 'source /opt/ros/humble/setup.bash && ros2 topic list | grep cmd_vel'
```
If missing, run clean-start-gazebo.sh

**Training hangs on "No sensor data":**
- Gazebo not running or robot not spawned
- Check `ros2 topic list` for `/scan` and `/odom`

**Training too slow:**
- Expected: ~30–50 steps per episode early on (with collisions)
- Gazebo runs faster without GUI (gzclient)
- CPU usage is normal (gzserver is compute-heavy)

---

## Next Steps

1. Let training run for 50–100 episodes
2. Monitor avg_reward trend (should improve over time)
3. Optionally start gzclient to visualize robot behavior
4. After 50 episodes, check `model_ep50.pt` checkpoint
5. Consider adjusting hyperparameters in `agent.py` if needed
