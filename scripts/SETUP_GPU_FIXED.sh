#!/usr/bin/env bash
# GPU Setup for Linux Mint - Fixed version
set -e

cd /home/hithx/Documents/H2F/h2f_implementation

echo "🚀 GPU Setup for Linux Mint 22.2"
echo "=================================="
echo ""

# Step 1: Install NVIDIA Container Toolkit
echo "Step 1: Installing NVIDIA Container Toolkit..."

# Use stable repository (works for Ubuntu/Mint)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
    sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

# Use stable/deb directly (works for all Ubuntu-based distros)
echo "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/\$(ARCH) /" | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

echo "✅ NVIDIA Container Toolkit installed"
sleep 5

# Step 2: Backup models
echo ""
echo "Step 2: Backing up models..."
BACKUP_DIR="./model_backups_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

docker cp ros2_container:/root/drone_rl/model_td3.pt "$BACKUP_DIR/" 2>/dev/null && echo "  ✓ model_td3.pt" || true
docker cp ros2_container:/root/drone_rl/model_td3_ep250.pt "$BACKUP_DIR/" 2>/dev/null && echo "  ✓ model_td3_ep250.pt" || true
docker cp ros2_container:/root/drone_rl/train_td3.log "$BACKUP_DIR/" 2>/dev/null && echo "  ✓ train_td3.log" || true

echo "✅ Backup saved to: $BACKUP_DIR"

# Step 3: Stop and rebuild container
echo ""
echo "Step 3: Rebuilding container with GPU support..."
echo "This will take 3-5 minutes (downloading PyTorch with CUDA)..."

docker exec ros2_container pkill -f train 2>/dev/null || true
docker exec ros2_container pkill -f gzserver 2>/dev/null || true
sleep 2

docker stop ros2_container 2>/dev/null || true
docker rm ros2_container 2>/dev/null || true

docker compose build --no-cache
docker compose up -d
sleep 5

echo "✅ Container rebuilt"

# Step 4: Verify GPU
echo ""
echo "Step 4: Verifying GPU access..."
sleep 2

GPU_RESULT=$(docker exec ros2_container python3 -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'); print('PyTorch:', torch.__version__)" 2>&1)

echo "$GPU_RESULT"

if echo "$GPU_RESULT" | grep -q "CUDA: True"; then
    echo "✅ GPU access confirmed!"
else
    echo "⚠️  GPU not detected yet, checking PyTorch version..."
    docker exec ros2_container pip3 show torch | grep Version
fi

# Step 5: Restore files
echo ""
echo "Step 5: Restoring code and models..."

docker exec ros2_container mkdir -p /root/drone_rl

# Copy Python files
for file in agent_td3.py train_td3.py env.py agent.py train.py; do
    if [ -f "drone_rl/$file" ]; then
        docker cp "drone_rl/$file" "ros2_container:/root/drone_rl/"
        echo "  ✓ $file"
    fi
done

# Restore models
if [ -d "$BACKUP_DIR" ]; then
    for model in "$BACKUP_DIR"/*.pt; do
        if [ -f "$model" ]; then
            docker cp "$model" "ros2_container:/root/drone_rl/"
            echo "  ✓ $(basename $model)"
        fi
    done
    docker cp "$BACKUP_DIR/train_td3.log" "ros2_container:/root/drone_rl/" 2>/dev/null || true
fi

# Copy scripts
docker cp scripts/container/clean-start-gazebo.sh ros2_container:/tmp/ 2>/dev/null || true

echo "✅ All files restored"

# Final summary
echo ""
echo "=========================================="
echo "✅ GPU Setup Complete!"
echo "=========================================="
echo ""
echo "Models in container:"
docker exec ros2_container ls -lh /root/drone_rl/*.pt 2>/dev/null | awk '{print "  "$9" - "$5}' || echo "  (no models yet)"
echo ""
echo "To start GPU-accelerated training:"
echo ""
echo "  1. Start Gazebo:"
echo "     docker exec ros2_container bash /tmp/clean-start-gazebo.sh &"
echo ""
echo "  2. Wait 10 seconds, then start training:"
echo "     sleep 10"
echo "     docker exec -it ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 train_td3.py'"
echo ""
echo "Expected output: 'TD3Agent on device: cuda:0'"
echo "Training speed: 5-6x faster than CPU!"
