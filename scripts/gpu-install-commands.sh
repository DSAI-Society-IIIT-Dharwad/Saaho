#!/usr/bin/env bash
# GPU Setup Commands - Run these in your terminal (will prompt for sudo password)

echo "=== Step 1: Install NVIDIA Container Toolkit ==="
echo "Run these commands:"
echo ""
cat << 'EOF'
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
EOF

echo ""
echo "=== Step 2: After Docker restarts, run: ==="
echo ""
echo "cd /home/hithx/Documents/H2F/h2f_implementation"
echo "./scripts/enable-gpu-no-sudo.sh"
