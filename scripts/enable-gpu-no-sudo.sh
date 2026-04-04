#!/usr/bin/env bash
# Part 2: Container rebuild and model restore (no sudo needed)
set -euo pipefail

cd /home/hithx/Documents/H2F/h2f_implementation

echo "🚀 GPU Setup Part 2: Container Rebuild"
echo "======================================"
echo ""

# Step 1: Backup models
echo "Step 1: Backing up trained models..."
BACKUP_DIR="./model_backups_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if docker exec ros2_container test -f /root/drone_rl/model_td3.pt 2>/dev/null; then
    docker cp ros2_container:/root/drone_rl/model_td3.pt "$BACKUP_DIR/" || true
    docker cp ros2_container:/root/drone_rl/model_td3_ep*.pt "$BACKUP_DIR/" 2>/dev/null || true
    docker cp ros2_container:/root/drone_rl/train_td3.log "$BACKUP_DIR/" 2>/dev/null || true
    echo "✅ Models backed up to $BACKUP_DIR"
    ls -lh "$BACKUP_DIR"
else
    echo "⚠️  No existing models found"
fi
echo ""

# Step 2: Stop training and container
echo "Step 2: Stopping current processes..."
docker exec ros2_container pkill -f train_td3 2>/dev/null || true
docker exec ros2_container pkill -f gzserver 2>/dev/null || true
sleep 2
docker stop ros2_container 2>/dev/null || true
docker rm ros2_container 2>/dev/null || true
echo "✅ Stopped"
echo ""

# Step 3: Rebuild container
echo "Step 3: Rebuilding container with GPU + CUDA PyTorch..."
echo "This will take 3-5 minutes (downloading PyTorch with CUDA)..."
docker compose build --no-cache

echo "✅ Build complete"
echo ""

# Step 4: Start container
echo "Step 4: Starting GPU-enabled container..."
docker compose up -d
sleep 3
echo "✅ Container running"
echo ""

# Step 5: Verify GPU
echo "Step 5: Verifying GPU access..."
GPU_CHECK=$(docker exec ros2_container python3 -c "import torch; print(torch.cuda.is_available())" 2>/dev/null || echo "false")

if [ "$GPU_CHECK" = "True" ]; then
    echo "✅ GPU access confirmed!"
    docker exec ros2_container python3 -c "
import torch
print(f'  CUDA available: {torch.cuda.is_available()}')
print(f'  Device: {torch.cuda.get_device_name(0)}')
print(f'  PyTorch: {torch.__version__}')
"
else
    echo "❌ GPU not accessible. Checking..."
    docker exec ros2_container python3 -c "import torch; print(torch.__version__)"
    echo "May need to wait for container to fully initialize. Try again in 10 seconds."
fi
echo ""

# Step 6: Restore files
echo "Step 6: Restoring code and models..."
docker exec ros2_container mkdir -p /root/drone_rl

# Copy Python files
for file in agent_td3.py train_td3.py env.py agent.py train.py; do
    if [ -f "drone_rl/$file" ]; then
        docker cp "drone_rl/$file" ros2_container:/root/drone_rl/
        echo "  ✓ $file"
    fi
done

# Restore models
if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR/*.pt 2>/dev/null)" ]; then
    for model in "$BACKUP_DIR"/*.pt; do
        docker cp "$model" ros2_container:/root/drone_rl/
        echo "  ✓ $(basename $model)"
    done
    docker cp "$BACKUP_DIR/train_td3.log" ros2_container:/root/drone_rl/ 2>/dev/null || true
fi

# Copy scripts
docker cp scripts/container/clean-start-gazebo.sh ros2_container:/tmp/ 2>/dev/null || true
docker cp scripts/container/run-training.sh ros2_container:/tmp/ 2>/dev/null || true

echo "✅ All files restored"
echo ""

# Final check
echo "==========================================="
echo "✅ GPU Setup Complete!"
echo "==========================================="
echo ""
echo "Models in container:"
docker exec ros2_container ls -lh /root/drone_rl/*.pt 2>/dev/null | awk '{print "  "$9" "$5}' || echo "  (no models)"
echo ""
echo "To start GPU-accelerated training:"
echo "  1. docker exec ros2_container bash /tmp/clean-start-gazebo.sh &"
echo "  2. sleep 10"
echo "  3. docker exec -it ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 train_td3.py'"
echo ""
echo "You should see: 'TD3Agent on device: cuda:0'"
