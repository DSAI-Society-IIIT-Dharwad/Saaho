# 🎯 Valid Goal Positions for TurtleBot3 World

## World Layout

The TurtleBot3 world (`turtlebot3_world.world`) is approximately **3.6m x 3.6m** with obstacles in the center.

```
         Y
         ↑
    -2  -1   0   1   2
    ┌───┬───┬───┬───┬───┐  2
    │ ✅ │ ✅ │ ❌ │ ✅ │ ✅ │
    ├───┼───┼───┼───┼───┤  1
    │ ✅ │ ✅ │ ❌ │ ✅ │ ✅ │
    ├───┼───┼───┼───┼───┤  0  → X
    │ ❌ │ ❌ │ 🚫 │ ❌ │ ❌ │
    ├───┼───┼───┼───┼───┤ -1
    │ ✅ │ ✅ │ ❌ │ ✅ │ ✅ │
    ├───┼───┼───┼───┼───┤ -2
    │ ✅ │ ✅ │ ❌ │ ✅ │ ✅ │
    └───┴───┴───┴───┴───┘

✅ = Safe goal area
❌ = Has obstacles or too close
🚫 = Center obstacle cluster
```

---

## ✅ SAFE Goal Coordinates (Try These!)

### Quadrant 1 (Top-Right)
- **(1.5, 1.5)** ← Default goal, always works
- **(1.0, 1.0)**
- **(2.0, 1.5)**
- **(1.5, 2.0)**

### Quadrant 2 (Top-Left)
- **(-1.5, 1.5)** ← Opposite corner
- **(-1.0, 1.0)**
- **(-2.0, 1.5)**
- **(-1.5, 2.0)**

### Quadrant 3 (Bottom-Left)
- **(-1.5, -1.5)** ← Clear area
- **(-1.0, -1.0)**
- **(-2.0, -1.5)**
- **(-1.5, -2.0)**

### Quadrant 4 (Bottom-Right)
- **(1.5, -1.5)** ← Clear area
- **(1.0, -1.0)**
- **(2.0, -1.5)**
- **(1.5, -2.0)**

---

## ❌ AVOID These Coordinates

### Center Area (Obstacles)
- **(0.0, 0.0)** ← Main obstacle cluster
- Anything with **|x| < 0.5 AND |y| < 0.5**

### Outside World Boundaries
- **x or y > 3.0** ← Too far
- **x or y < -3.0** ← Too far

### Examples of BAD goals:
- ❌ (5, 5) - Outside world
- ❌ (4, 3) - Outside world
- ❌ (0, 0) - Center obstacles
- ❌ (6, 2) - Way outside
- ❌ (0.2, 0.2) - Too close to center

---

## 🎮 How to Set Goals in RViz

1. **Check Current Robot Position:**
   - Look at the green/red axes in RViz (that's the robot)
   - Note the coordinates

2. **Click Nav2 Goal Tool:**
   - Find the button in the toolbar (usually an arrow icon)
   - Click it to activate

3. **Set Goal in SAFE ZONE:**
   - Click on a **safe area** (see green zones above)
   - Stay away from the center (0, 0)
   - Keep coordinates between -2.5 and 2.5

4. **Drag to Set Orientation:**
   - After clicking, drag a bit to set which way the robot should face
   - Direction doesn't matter much for this demo

---

## 🧪 Quick Test Sequence

Try these goals in order to test all quadrants:

1. **(1.5, 1.5)** - Top-right (default)
2. **(-1.5, 1.5)** - Top-left
3. **(-1.5, -1.5)** - Bottom-left
4. **(1.5, -1.5)** - Bottom-right
5. **(0, 2)** - North (careful!)
6. **(2, 0)** - East (careful!)

The robot should successfully navigate to all of these!

---

## 📊 Understanding the Behavior

### What Happens When You Set a Goal:

1. **Goal Received** → Demo logs: `🎯 New goal received: (x, y)`
2. **Robot Navigates** → Uses trained TD3 policy
3. **Success** → Demo logs: `🎯 Goal reached at (x, y)!`
4. **Or Collision** → Demo logs: `💥 Collision!`
5. **Auto-Reset** → World resets to spawn position (-2, -0.5)
6. **Continues** → Robot navigates to goal again

### If Robot Gets Stuck in Collision Loop:

Reset the world manually:
```bash
docker exec ros2_container bash -c 'source /opt/ros/humble/setup.bash && ros2 service call /reset_world std_srvs/srv/Empty'
```

Then set a **SAFE** goal from the list above!

---

## 🎯 Pro Tips

1. **Start with the default goal (1.5, 1.5)** - Always works
2. **Stay away from x=0, y=0** - That's where obstacles are
3. **Keep |x| and |y| < 2.5** - Stay in bounds
4. **Watch the laser scans in RViz** - Red dots show obstacles
5. **If robot is stuck** - Reset world and try a different goal

---

**Current Robot Spawn:** **(-2.0, -0.5)** after each reset  
**Recommended First Goal:** **(1.5, 1.5)** (top-right, always clear)
