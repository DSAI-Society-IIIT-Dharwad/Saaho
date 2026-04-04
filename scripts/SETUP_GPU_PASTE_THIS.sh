#!/usr/bin/env bash
# Copy and paste this ENTIRE block into your terminal
# It will prompt for sudo password once

set -e
cd /home/hithx/Documents/H2F/h2f_implementation

echo "🚀 GPU Setup - Step 1: Install NVIDIA Container Toolkit"
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
echo "✅ Docker restarted with GPU support"
sleep 5

echo ""
echo "🚀 Step 2: Backup models and rebuild container"
BACKUP_DIR="./model_backups_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
docker cp ros2_container:/root/drone_rl/model_td3.pt "$BACKUP_DIR/" 2>/dev/null || true
docker cp ros2_container:/root/drone_rl/model_td3_ep250.pt "$BACKUP_DIR/" 2>/dev/null || true
docker cp ros2_container:/root/drone_rl/train_td3.log "$BACKUP_DIR/" 2>/dev/null || true
echo "✅ Models backed up to $BACKUP_DIR"

echo ""
echo "🚀 Step 3: Stop and rebuild container (3-5 minutes)"
docker exec ros2_container pkill -f train 2>/dev/null || true
docker exec ros2_container pkill -f gzserver 2>/dev/null || true
sleep 2
docker stop ros2_container && docker rm ros2_container
docker compose build --no-cache
docker compose up -d
sleep 5

echo ""
echo "🚀 Step 4: Verify GPU and restore files"
docker exec ros2_container python3 -c "import torch; print('CUDA:', torch.cuda.is_available(), '|', 'GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"

docker exec ros2_container mkdir -p /root/drone_rl
docker cp drone_rl/agent_td3.py ros2_container:/root/drone_rl/
docker cp drone_rl/train_td3.py ros2_container:/root/drone_rl/
docker cp drone_rl/env.py ros2_container:/root/drone_rl/
docker cp "$BACKUP_DIR"/*.pt ros2_container:/root/drone_rl/ 2>/dev/null || true
docker cp scripts/container/clean-start-gazebo.sh ros2_container:/tmp/ 2>/dev/null || true

echo ""
echo "✅ GPU Setup Complete!"
echo ""
echo "Start GPU training:"
echo "  docker exec ros2_container bash /tmp/clean-start-gazebo.sh &"
echo "  sleep 10"
echo "  docker exec -it ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 train_td3.py'"
