# 🎮 Interactive Demo — Trained TD3 Agent

## What's Running Now

✅ **Gazebo GUI** — 3D visualization of TurtleBot3 world  
✅ **RViz** — Robot visualization and goal setting tool  
✅ **Trained Agent** — Autonomous navigation using TD3 model  

---

## How to Use

### 1. Gazebo Window

You should see:
- TurtleBot3 burger robot
- Obstacle world
- Robot moving smoothly toward goal

**Watch the smooth continuous motion!** (vs jerky discrete actions)

### 2. RViz Window

**Setup RViz (first time):**
1. Set **Fixed Frame** → `odom`
2. Click **Add** (bottom left)
3. Add **LaserScan** → Topic `/scan`
4. Add **RobotModel** (optional)
5. Add **Path** → Topic `/odom` (to see trajectory)

**Set Custom Goals:**
1. Click toolbar button **"2D Goal Pose"** (arrow icon)
2. Click anywhere in RViz to set goal position
3. Drag to set orientation
4. Watch robot navigate to your goal!

### 3. Current Status

The agent is running continuously and reaching goals. It already reached the default goal (1.5, 1.5) multiple times.

**Try setting new goals in RViz to test different positions!**

---

## What You Can Test

### Easy Goals (Wide Open Space)
- (2.0, 0.0)
- (0.0, 2.0)
- (-1.0, -1.0)

### Moderate Goals (Near Obstacles)
- (1.0, -1.5)
- (-1.5, 1.0)

### Challenging Goals (Through Narrow Passages)
- Set goals that require navigating around obstacles
- Agent should smoothly avoid collisions

---

## Commands Quick Reference

### Stop Demo
```bash
docker exec ros2_container pkill -f demo_trained_agent
```

### Restart Demo
```bash
docker exec ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 demo_trained_agent.py'
```

### Test Specific Goal from Command Line
```bash
# Navigate to (2.0, -1.0)
docker exec ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 test_interactive.py 2.0 -1.0'
```

### Close Windows
```bash
# Close Gazebo GUI
docker exec ros2_container pkill gzclient

# Close RViz
docker exec ros2_container pkill rviz2

# Restart if needed
docker exec -e DISPLAY=:0 ros2_container bash -lc 'source /opt/ros/humble/setup.bash && gzclient' &
docker exec -e DISPLAY=:0 ros2_container bash -lc 'source /opt/ros/humble/setup.bash && rviz2' &
```

---

## What to Observe

### Smooth Continuous Control
- Robot moves forward **while** turning (not stop-turn-move)
- Smooth arcs around obstacles
- Natural acceleration/deceleration

### Collision Avoidance
- Slows down near walls
- Maintains safe distance
- Finds alternative paths

### Goal-Directed Behavior
- Moves toward goal efficiently
- Corrects heading errors smoothly
- Stops at goal (within 0.3m radius)

---

## Monitor Demo

```bash
# Watch demo output
docker exec -it ros2_container tail -f /root/drone_rl/demo.log

# Check GPU usage during inference
nvidia-smi
```

---

## Compare with Random Agent

To see how much it learned, try random actions:

```python
# In demo, replace:
action = agent.select_action(state, add_noise=False)

# With:
action = np.array([
    np.random.uniform(0.0, 0.22),
    np.random.uniform(-2.0, 2.0)
])
```

You'll see it crash immediately!

---

## Performance

Your trained agent:
- ✅ 100% success rate in testing
- ✅ ~280 steps average to goal
- ✅ Zero collisions in 10 tests
- ✅ Smooth continuous trajectories
- ✅ GPU-accelerated inference

---

## Tips

1. **Set challenging goals** — Test obstacle avoidance
2. **Watch laser scan** in RViz — See how it reacts
3. **Try opposite corner** — (-2, -2) for longest path
4. **Multiple goals** — Set new goal immediately after reaching one
5. **Record video** — Use RViz or Gazebo built-in recording

---

## Stop Everything

```bash
docker exec ros2_container pkill -f demo_trained
docker exec ros2_container pkill -f gzclient
docker exec ros2_container pkill -f rviz2
```

---

## Summary

**Demo Status:** ✅ Running  
**Windows:** Gazebo + RViz should be visible  
**Agent:** Using trained TD3 model on GPU  
**Interactive:** Set goals with RViz "2D Goal Pose"  

Enjoy testing your trained navigation agent! 🎯
