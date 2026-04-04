#!/usr/bin/env bash
# Automated GPU setup: install toolkit, rebuild container, restore models.
# Run on HOST (not inside container).

set -euo pipefail

echo "🚀 GPU Acceleration Setup for TD3 Training"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "⚠️  Don't run as root. Run as regular user (will ask for sudo when needed)."
   exit 1
fi

# Check if GPU exists
if ! nvidia-smi &>/dev/null; then
    echo "❌ nvidia-smi not found. Is NVIDIA driver installed?"
    exit 1
fi

echo "✅ GPU detected:"
nvidia-smi --query-gpu=name --format=csv,noheader
echo ""

# Step 1: Check/Install NVIDIA Container Toolkit
echo "Step 1: Checking NVIDIA Container Toolkit..."
if ! command -v nvidia-container-runtime &>/dev/null; then
    echo "➜ Installing nvidia-container-toolkit (requires sudo)..."
    
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    
    curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    
    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit
    
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
    
    echo "✅ NVIDIA Container Toolkit installed"
else
    echo "✅ NVIDIA Container Toolkit already installed"
fi
echo ""

# Step 2: Backup models
echo "Step 2: Backing up trained models..."
BACKUP_DIR="./model_backups_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if docker exec ros2_container test -f /root/drone_rl/model_td3.pt 2>/dev/null; then
    docker cp ros2_container:/root/drone_rl/model_td3.pt "$BACKUP_DIR/" || true
    docker cp ros2_container:/root/drone_rl/model_td3_ep*.pt "$BACKUP_DIR/" 2>/dev/null || true
    echo "✅ Models backed up to $BACKUP_DIR"
else
    echo "⚠️  No existing models found (ok if first run)"
fi
echo ""

# Step 3: Rebuild container
echo "Step 3: Rebuilding container with GPU + CUDA PyTorch..."
echo "➜ Stopping current container..."
docker stop ros2_container 2>/dev/null || true
docker rm ros2_container 2>/dev/null || true

echo "➜ Building new image (this will take a few minutes)..."
docker compose build --no-cache

echo "➜ Starting GPU-enabled container..."
docker compose up -d

# Wait for container to be ready
sleep 3
echo "✅ Container rebuilt and running"
echo ""

# Step 4: Verify GPU access
echo "Step 4: Verifying GPU access in container..."
GPU_CHECK=$(docker exec ros2_container python3 -c "import torch; print(torch.cuda.is_available())" 2>/dev/null || echo "false")

if [ "$GPU_CHECK" = "True" ]; then
    GPU_NAME=$(docker exec ros2_container python3 -c "import torch; print(torch.cuda.get_device_name(0))" 2>/dev/null)
    echo "✅ GPU access confirmed: $GPU_NAME"
else
    echo "❌ GPU not accessible in container. Check docker-compose.yml GPU config."
    exit 1
fi
echo ""

# Step 5: Copy code and restore models
echo "Step 5: Copying training code and restoring models..."
docker exec ros2_container mkdir -p /root/drone_rl

# Copy Python files
for file in agent_td3.py train_td3.py env.py agent.py train.py; do
    if [ -f "drone_rl/$file" ]; then
        docker cp "drone_rl/$file" ros2_container:/root/drone_rl/
    fi
done

# Restore models
if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR/*.pt 2>/dev/null)" ]; then
    docker cp "$BACKUP_DIR"/. ros2_container:/root/drone_rl/
    echo "✅ Models and code restored"
else
    echo "⚠️  No models to restore (ok if starting fresh)"
fi
echo ""

# Step 6: Copy helper scripts
echo "Step 6: Copying helper scripts..."
if [ -f "scripts/container/clean-start-gazebo.sh" ]; then
    docker cp scripts/container/clean-start-gazebo.sh ros2_container:/tmp/
fi
if [ -f "scripts/container/run-training.sh" ]; then
    docker cp scripts/container/run-training.sh ros2_container:/tmp/
fi
echo "✅ Scripts copied"
echo ""

# Final summary
echo "=========================================="
echo "✅ GPU Setup Complete!"
echo "=========================================="
echo ""
echo "GPU Status:"
docker exec ros2_container python3 -c "
import torch
print(f'  CUDA available: {torch.cuda.is_available()}')
print(f'  Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')
print(f'  PyTorch version: {torch.__version__}')
"
echo ""
echo "Saved models location:"
if [ -d "$BACKUP_DIR" ]; then
    echo "  Host: $BACKUP_DIR"
fi
echo "  Container: /root/drone_rl/"
docker exec ros2_container ls -lh /root/drone_rl/*.pt 2>/dev/null | awk '{print "    "$9" "$5}' || echo "    (no models yet)"
echo ""
echo "Next steps:"
echo "  1. Start Gazebo:  docker exec ros2_container bash /tmp/clean-start-gazebo.sh &"
echo "  2. Wait 10 sec:   sleep 10"
echo "  3. Start training:"
echo "     docker exec -it ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 train_td3.py'"
echo ""
echo "Expected speed: 5-6x faster than CPU!"
