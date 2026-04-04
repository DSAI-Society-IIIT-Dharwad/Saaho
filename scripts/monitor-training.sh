#!/bin/bash
# Monitor diverse training progress

echo "=== Diverse Training Monitor ==="
echo ""

# Check if training is running
if docker exec ros2_container bash -c 'pgrep -f "train_td3.py.*random-goals"' > /dev/null 2>&1; then
    echo "✅ Training is RUNNING"
    echo ""
    
    # Show last 30 lines of log
    echo "📊 Recent Progress:"
    echo "---"
    docker exec ros2_container bash -c 'tail -30 /root/drone_rl/train_layout1.log 2>/dev/null' | grep -E "(Ep |Goal reached|reward=|Using random goals)"
    echo "---"
    echo ""
    
    # Count goals reached
    goal_count=$(docker exec ros2_container bash -c 'grep -c "Goal reached" /root/drone_rl/train_layout1.log 2>/dev/null || echo 0')
    echo "🎯 Goals reached so far: $goal_count"
    echo ""
    
    # Check for saved models
    echo "💾 Saved checkpoints:"
    docker exec ros2_container bash -c 'ls -lh /root/drone_rl/model_td3_diverse*.pt 2>/dev/null | tail -5 || echo "None yet (saves every 50 episodes)"'
    
else
    echo "❌ Training is NOT running"
    echo ""
    echo "Last log output:"
    docker exec ros2_container bash -c 'tail -20 /root/drone_rl/train_layout1.log 2>/dev/null || echo "No log file"'
fi

echo ""
echo "---"
echo "Run this script again to check progress: bash scripts/monitor-training.sh"
