#!/usr/bin/env bash
# GPU Setup - Bypass Cursor repo issue
set -e
cd /home/hithx/Documents/H2F/h2f_implementation

echo "🚀 GPU Setup (Fixed for repo issues)"
echo "====================================="
echo ""

# Step 1: Install nvidia-container-toolkit (bypass cursor repo)
echo "Step 1: Installing NVIDIA Container Toolkit..."
echo "Using direct package download to bypass repository issues..."

# Download packages directly
mkdir -p /tmp/nvidia-toolkit
cd /tmp/nvidia-toolkit

wget https://nvidia.github.io/libnvidia-container/stable/deb/amd64/libnvidia-container1_1.16.2-1_amd64.deb
wget https://nvidia.github.io/libnvidia-container/stable/deb/amd64/libnvidia-container-tools_1.16.2-1_amd64.deb
wget https://nvidia.github.io/libnvidia-container/stable/deb/amd64/nvidia-container-toolkit-base_1.16.2-1_amd64.deb
wget https://nvidia.github.io/libnvidia-container/stable/deb/amd64/nvidia-container-toolkit_1.16.2-1_amd64.deb

# Install packages
sudo dpkg -i libnvidia-container1_1.16.2-1_amd64.deb
sudo dpkg -i libnvidia-container-tools_1.16.2-1_amd64.deb
sudo dpkg -i nvidia-container-toolkit-base_1.16.2-1_amd64.deb
sudo dpkg -i nvidia-container-toolkit_1.16.2-1_amd64.deb

cd /home/hithx/Documents/H2F/h2f_implementation

echo "✅ NVIDIA Container Toolkit installed"

# Configure Docker
echo "Configuring Docker runtime..."
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
echo "✅ Docker restarted with GPU support"
sleep 5

# Step 2: Backup models
echo ""
echo "Step 2: Backing up models..."
BACKUP_DIR="./model_backups_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

docker cp ros2_container:/root/drone_rl/model_td3.pt "$BACKUP_DIR/" 2>/dev/null && echo "  ✓ model_td3.pt" || true
docker cp ros2_container:/root/drone_rl/model_td3_ep250.pt "$BACKUP_DIR/" 2>/dev/null && echo "  ✓ model_td3_ep250.pt" || true
docker cp ros2_container:/root/drone_rl/train_td3.log "$BACKUP_DIR/" 2>/dev/null || true

echo "✅ Backup: $BACKUP_DIR"

# Step 3: Rebuild container
echo ""
echo "Step 3: Rebuilding container (3-5 min)..."
docker exec ros2_container pkill -f train 2>/dev/null || true
docker exec ros2_container pkill -f gzserver 2>/dev/null || true
sleep 2
docker stop ros2_container && docker rm ros2_container

docker compose build --no-cache
docker compose up -d
sleep 5

echo "✅ Container rebuilt"

# Step 4: Verify GPU
echo ""
echo "Step 4: Verifying GPU..."
docker exec ros2_container python3 -c "import torch; print('CUDA:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None', '| PyTorch:', torch.__version__)"

# Step 5: Restore files
echo ""
echo "Step 5: Restoring files..."
docker exec ros2_container mkdir -p /root/drone_rl

for file in agent_td3.py train_td3.py env.py agent.py train.py; do
    [ -f "drone_rl/$file" ] && docker cp "drone_rl/$file" "ros2_container:/root/drone_rl/" && echo "  ✓ $file"
done

for model in "$BACKUP_DIR"/*.pt; do
    [ -f "$model" ] && docker cp "$model" "ros2_container:/root/drone_rl/" && echo "  ✓ $(basename $model)"
done

docker cp scripts/container/clean-start-gazebo.sh ros2_container:/tmp/ 2>/dev/null || true

echo ""
echo "✅ COMPLETE!"
echo ""
echo "Start training:"
echo "  docker exec ros2_container bash /tmp/clean-start-gazebo.sh &"
echo "  sleep 10"
echo "  docker exec -it ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 train_td3.py'"
