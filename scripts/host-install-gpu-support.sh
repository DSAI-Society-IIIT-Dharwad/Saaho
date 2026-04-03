#!/usr/bin/env bash
# Install NVIDIA Container Toolkit to enable GPU access in Docker containers.
# Run this on the HOST (not inside container).

set -euo pipefail

echo "🚀 Installing NVIDIA Container Toolkit for Docker GPU support..."

# Add NVIDIA Container Toolkit repository
echo "➜ Adding NVIDIA repository..."
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install
echo "➜ Installing nvidia-container-toolkit..."
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker
echo "➜ Configuring Docker to use nvidia runtime..."
sudo nvidia-ctk runtime configure --runtime=docker

# Restart Docker
echo "➜ Restarting Docker daemon..."
sudo systemctl restart docker

echo ""
echo "✅ NVIDIA Container Toolkit installed successfully!"
echo ""
echo "Verify with:"
echo "  docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi"
