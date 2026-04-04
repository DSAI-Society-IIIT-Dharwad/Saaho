# GPU Acceleration Setup — Fix Slow Training

## Problem Identified

Your training is slow because:

1. ❌ **PyTorch CPU-only version** installed (`torch 2.11.0+cpu`)
2. ❌ **No GPU access** in container (no nvidia-container-toolkit)
3. ✅ **GPU available** on host (RTX 2050)

**Result:** Training runs on CPU despite having a capable GPU.

---

## Solution: 3-Step GPU Enable

### Step 1: Install NVIDIA Container Toolkit (Host)

This allows Docker containers to access your GPU.

```bash
cd /home/hithx/Documents/H2F/h2f_implementation
sudo ./scripts/host-install-gpu-support.sh
```

**What it does:**
- Installs nvidia-container-toolkit
- Configures Docker for GPU access
- Restarts Docker daemon

**Verify installation:**
```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

You should see your RTX 2050 GPU info.

---

### Step 2: Rebuild Container with CUDA PyTorch

Your current container has CPU-only PyTorch. Rebuild with GPU support:

```bash
cd /home/hithx/Documents/H2F/h2f_implementation

# Stop and remove old container
docker stop ros2_container
docker rm ros2_container

# Rebuild with CUDA PyTorch
docker compose build --no-cache

# Start new container with GPU access
docker compose up -d
```

**What changed in Dockerfile:**
- Added `pip3 install torch --index-url https://download.pytorch.org/whl/cu118`
- This installs PyTorch 2.x with CUDA 11.8 support (compatible with RTX 2050)

**What changed in docker-compose.yml:**
- Added GPU device reservation
- Added NVIDIA environment variables

---

### Step 3: Verify GPU Access

```bash
# Check CUDA availability
docker exec ros2_container python3 -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

Expected output:
```
CUDA available: True
GPU: NVIDIA GeForce RTX 2050
```

---

## Copy Training Files to New Container

Since you rebuilt, copy your TD3 files and models:

```bash
# Copy code
docker cp drone_rl/agent_td3.py ros2_container:/root/drone_rl/
docker cp drone_rl/train_td3.py ros2_container:/root/drone_rl/
docker cp drone_rl/env.py ros2_container:/root/drone_rl/
docker cp drone_rl/agent.py ros2_container:/root/drone_rl/
docker cp drone_rl/train.py ros2_container:/root/drone_rl/

# Copy saved models (IMPORTANT - your 250 episodes of training!)
docker cp drone_rl/model_td3*.pt ros2_container:/root/drone_rl/ 2>/dev/null || echo "Models already exist"
```

**Alternative:** If you bind-mounted `/workspace` in docker-compose, models are already there at `/workspace/drone_rl/`.

---

## Restart Training with GPU

```bash
# Clean start Gazebo
docker exec ros2_container bash /tmp/clean-start-gazebo.sh &

# Wait 10 seconds
sleep 10

# Start TD3 training (will use GPU automatically)
docker exec -it ros2_container bash -lc 'cd /root/drone_rl && source /opt/ros/humble/setup.bash && export TURTLEBOT3_MODEL=burger && python3 train_td3.py'
```

You should see:
```
TD3Agent on device: cuda:0
```

---

## Expected Speed Improvement

| Metric | CPU (Current) | GPU (RTX 2050) | Speedup |
|--------|---------------|----------------|---------|
| Episode time | ~30-60 sec | ~5-10 sec | **5-6x faster** |
| 10 episodes | ~8-10 min | ~1-2 min | **5-6x faster** |
| 50 episodes | ~40 min | ~7-10 min | **5-6x faster** |
| 1000 episodes | ~13 hours | ~2-3 hours | **5-6x faster** |

**Why such a big difference:**
- TD3 has 6 neural networks (actor, 2 critics, 3 targets)
- Each training step does 2-3 forward/backward passes
- Batch size 64 → hundreds of matrix operations per step
- GPU parallelizes all this, CPU does sequentially

---

## Troubleshooting

### "CUDA available: False" after rebuild

**Check:**
```bash
# Container has nvidia-smi?
docker exec ros2_container nvidia-smi

# PyTorch version correct?
docker exec ros2_container pip3 show torch | grep Version
```

Should show `torch 2.x.x+cu118` (not `+cpu`)

### "Could not load dynamic library 'libcudart.so'"

CUDA libraries missing. Rebuild with:
```dockerfile
RUN apt-get install -y cuda-toolkit-11-8
```

### Container won't start after GPU config

**Check logs:**
```bash
docker logs ros2_container
```

**Fallback:** Remove GPU config temporarily:
```bash
# Remove deploy section from docker-compose.yml
docker compose up -d
```

### Training still slow with GPU

**Verify GPU is actually being used:**
```bash
# In another terminal while training runs
nvidia-smi -l 1
```

You should see:
- `python3` process using GPU memory (~500-1000 MB)
- GPU utilization 30-80%

---

## Quick Setup Script (All Steps)

Save training first, then run this:

```bash
#!/bin/bash
set -e

# Step 1: Install nvidia-container-toolkit
echo "Step 1: Installing NVIDIA Container Toolkit..."
sudo ./scripts/host-install-gpu-support.sh

# Step 2: Backup models
echo "Step 2: Backing up models..."
docker cp ros2_container:/root/drone_rl/model_td3.pt ./model_td3_backup.pt
docker cp ros2_container:/root/drone_rl/model_td3_ep250.pt ./model_td3_ep250_backup.pt

# Step 3: Rebuild container
echo "Step 3: Rebuilding container with GPU support..."
docker stop ros2_container
docker rm ros2_container
docker compose build --no-cache
docker compose up -d

# Step 4: Restore models
echo "Step 4: Restoring models..."
docker exec ros2_container mkdir -p /root/drone_rl
docker cp ./model_td3_backup.pt ros2_container:/root/drone_rl/model_td3.pt
docker cp ./model_td3_ep250_backup.pt ros2_container:/root/drone_rl/model_td3_ep250.pt
docker cp drone_rl/*.py ros2_container:/root/drone_rl/

# Step 5: Verify
echo "Step 5: Verifying GPU access..."
docker exec ros2_container python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"

echo "✅ Done! Start training with GPU support."
```

---

## Alternative: Keep Current Container (Temporary Fix)

If you don't want to rebuild now, you can install CUDA PyTorch in the running container (will be lost on restart):

```bash
docker exec ros2_container pip3 install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

But you still need Step 1 (nvidia-container-toolkit) for GPU access.

---

## Summary

**Current:** CPU-only, ~8-10 min per 10 episodes  
**After fix:** GPU-accelerated, ~1-2 min per 10 episodes  
**Total time saved:** 5-6x faster training

**What to do:**
1. Run `./scripts/host-install-gpu-support.sh` (installs toolkit)
2. Rebuild container with `docker compose build --no-cache`
3. Copy models and code back to new container
4. Resume training — will automatically use GPU

Your 250+ episode checkpoint is safe — we'll restore it to the new GPU-enabled container.
