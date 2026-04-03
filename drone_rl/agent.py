"""
agent.py — DQN agent with Experience Replay for TurtleBot3 navigation.

Architecture: MLP  input(26) → 256 → 256 → 3 actions
Uses: Double DQN + target network soft update
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random
from collections import deque

# ── Hyper-parameters ──────────────────────────────────────────────────────────
MEMORY_SIZE   = 50_000
BATCH_SIZE    = 64
GAMMA         = 0.99      # discount factor
LR            = 1e-3      # learning rate
EPS_START     = 1.0       # exploration start
EPS_END       = 0.05      # exploration minimum
EPS_DECAY     = 0.995     # per-episode decay
TAU           = 0.005     # soft target-network update weight


# ── Neural Network ─────────────────────────────────────────────────────────────
class DQNNet(nn.Module):
    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, action_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ── Replay Buffer ──────────────────────────────────────────────────────────────
class ReplayBuffer:
    def __init__(self, capacity: int):
        self.buf = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buf.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int):
        batch = random.sample(self.buf, batch_size)
        s, a, r, ns, d = zip(*batch)
        return (np.array(s, dtype=np.float32),
                np.array(a, dtype=np.int64),
                np.array(r, dtype=np.float32),
                np.array(ns, dtype=np.float32),
                np.array(d, dtype=np.float32))

    def __len__(self):
        return len(self.buf)


# ── DQN Agent ──────────────────────────────────────────────────────────────────
class DQNAgent:
    def __init__(self, state_dim: int, action_dim: int):
        self.device     = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.action_dim = action_dim
        self.epsilon    = EPS_START

        self.policy_net = DQNNet(state_dim, action_dim).to(self.device)
        self.target_net = DQNNet(state_dim, action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=LR)
        self.memory    = ReplayBuffer(MEMORY_SIZE)
        self.loss_fn   = nn.SmoothL1Loss()   # Huber loss

        print(f"DQNAgent on device: {self.device}")
        print(f"State dim: {state_dim}  |  Action dim: {action_dim}")

    # ── action selection ──────────────────────────────────────────────────────
    def select_action(self, state: np.ndarray) -> int:
        if random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)
        with torch.no_grad():
            s = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            return int(self.policy_net(s).argmax(dim=1).item())

    def decay_epsilon(self):
        self.epsilon = max(EPS_END, self.epsilon * EPS_DECAY)

    # ── training step ──────────────────────────────────────────────────────────
    def train_step(self) -> float | None:
        if len(self.memory) < BATCH_SIZE:
            return None

        s, a, r, ns, d = self.memory.sample(BATCH_SIZE)
        s  = torch.FloatTensor(s).to(self.device)
        a  = torch.LongTensor(a).to(self.device)
        r  = torch.FloatTensor(r).to(self.device)
        ns = torch.FloatTensor(ns).to(self.device)
        d  = torch.FloatTensor(d).to(self.device)

        # Current Q values
        curr_q = self.policy_net(s).gather(1, a.unsqueeze(1)).squeeze(1)

        # Double DQN target
        with torch.no_grad():
            best_actions = self.policy_net(ns).argmax(dim=1, keepdim=True)
            next_q = self.target_net(ns).gather(1, best_actions).squeeze(1)
            target_q = r + GAMMA * next_q * (1 - d)

        loss = self.loss_fn(curr_q, target_q)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.policy_net.parameters(), 10.0)
        self.optimizer.step()

        # Soft update target network
        for p, tp in zip(self.policy_net.parameters(),
                         self.target_net.parameters()):
            tp.data.copy_(TAU * p.data + (1 - TAU) * tp.data)

        return loss.item()

    # ── persistence ───────────────────────────────────────────────────────────
    def save(self, path: str = "model.pt"):
        torch.save(self.policy_net.state_dict(), path)
        print(f"Model saved → {path}")

    def load(self, path: str = "model.pt"):
        self.policy_net.load_state_dict(torch.load(path, map_location=self.device))
        self.target_net.load_state_dict(self.policy_net.state_dict())
        print(f"Model loaded ← {path}")
