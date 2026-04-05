"""
agent_td3.py — TD3 (Twin Delayed DDPG) agent for continuous action control.

Architecture:
  Actor:  state(26) → 256 → 256 → action(2) with tanh
  Critic: state(26) + action(2) → 256 → 256 → Q-value
  Uses two critics (clipped double Q-learning) + delayed policy updates

Action space: [linear_vel, angular_vel] ∈ [0, 0.3] × [-1.0, 1.0]
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random
from collections import deque

# ── Hyper-parameters ──────────────────────────────────────────────────────────
MEMORY_SIZE    = 100_000
BATCH_SIZE     = 64
GAMMA          = 0.99       # discount factor
LR_ACTOR       = 1e-4       # actor learning rate
LR_CRITIC      = 3e-4       # critic learning rate
TAU            = 0.005      # soft target update weight
POLICY_DELAY   = 2          # update actor every N critic updates
NOISE_CLIP     = 0.5        # target policy smoothing noise clip
EXPLORATION_NOISE = 0.1     # action exploration noise (Gaussian)

# Action bounds (TurtleBot3 burger limits)
LINEAR_MIN  = 0.0
LINEAR_MAX  = 0.5     # TurtleBot3 max pushed slightly to 0.5 m/s
ANGULAR_MIN = -2.84
ANGULAR_MAX = 2.84      # TurtleBot3 max ~2.84 rad/s


# ── Actor Network ──────────────────────────────────────────────────────────────
class Actor(nn.Module):
    """Policy network: state → continuous action."""
    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, action_dim),
            nn.Tanh(),  # output in [-1, 1]
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        return self.net(state)


# ── Critic Network ─────────────────────────────────────────────────────────────
class Critic(nn.Module):
    """Q-network: (state, action) → Q-value."""
    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim + action_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, 1),
        )

    def forward(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([state, action], dim=1))


# ── Replay Buffer ──────────────────────────────────────────────────────────────
class ReplayBuffer:
    def __init__(self, capacity: int):
        self.buf = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buf.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int):
        batch = random.sample(self.buf, batch_size)
        s, a, r, ns, d = zip(*batch)
        return (
            np.array(s, dtype=np.float32),
            np.array(a, dtype=np.float32),
            np.array(r, dtype=np.float32),
            np.array(ns, dtype=np.float32),
            np.array(d, dtype=np.float32),
        )

    def __len__(self):
        return len(self.buf)


# ── TD3 Agent ──────────────────────────────────────────────────────────────────
class DDPGAgent:
    def __init__(self, state_dim: int, action_dim: int = 2):
        self.device     = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.action_dim = action_dim
        self.updates    = 0  # track critic updates for delayed policy

        # Actor + target
        self.actor        = Actor(state_dim, action_dim).to(self.device)
        self.actor_target = Actor(state_dim, action_dim).to(self.device)
        self.actor_target.load_state_dict(self.actor.state_dict())
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=LR_ACTOR)

        # Twin critics + targets
        self.critic1        = Critic(state_dim, action_dim).to(self.device)
        self.critic2        = Critic(state_dim, action_dim).to(self.device)
        self.critic1_target = Critic(state_dim, action_dim).to(self.device)
        self.critic2_target = Critic(state_dim, action_dim).to(self.device)
        self.critic1_target.load_state_dict(self.critic1.state_dict())
        self.critic2_target.load_state_dict(self.critic2.state_dict())
        self.critic_optimizer = optim.Adam(
            list(self.critic1.parameters()) + list(self.critic2.parameters()),
            lr=LR_CRITIC,
        )

        self.memory = ReplayBuffer(MEMORY_SIZE)

        print(f"TD3Agent on device: {self.device}")
        print(f"State dim: {state_dim}  |  Action dim: {action_dim}")
        print(f"Linear vel: [{LINEAR_MIN}, {LINEAR_MAX}]  "
              f"Angular vel: [{ANGULAR_MIN}, {ANGULAR_MAX}]")

    # ── action selection ──────────────────────────────────────────────────────
    def select_action(self, state: np.ndarray, add_noise: bool = True) -> np.ndarray:
        """
        Returns action [linear_vel, angular_vel].
        add_noise=True for training (exploration), False for evaluation.
        """
        with torch.no_grad():
            s = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action = self.actor(s).cpu().numpy()[0]  # shape (2,) in [-1, 1]

        if add_noise:
            noise = np.random.normal(0, EXPLORATION_NOISE, size=self.action_dim)
            action = np.clip(action + noise, -1.0, 1.0)

        # Scale from [-1,1] to actual ranges
        linear  = self._scale(action[0], LINEAR_MIN, LINEAR_MAX)
        angular = self._scale(action[1], ANGULAR_MIN, ANGULAR_MAX)
        return np.array([linear, angular], dtype=np.float32)

    @staticmethod
    def _scale(val: float, low: float, high: float) -> float:
        """Scale from [-1, 1] to [low, high]."""
        return low + (val + 1.0) * 0.5 * (high - low)

    @staticmethod
    def _unscale(val: float, low: float, high: float) -> float:
        """Scale from [low, high] to [-1, 1]."""
        return 2.0 * (val - low) / (high - low) - 1.0

    # ── training step ──────────────────────────────────────────────────────────
    def train_step(self) -> dict | None:
        """
        Returns dict with 'critic_loss' and optionally 'actor_loss'.
        """
        if len(self.memory) < BATCH_SIZE:
            return None

        s, a, r, ns, d = self.memory.sample(BATCH_SIZE)
        s  = torch.FloatTensor(s).to(self.device)
        ns = torch.FloatTensor(ns).to(self.device)
        r  = torch.FloatTensor(r).to(self.device)
        d  = torch.FloatTensor(d).to(self.device)

        # Unscale actions from [low, high] to [-1, 1] for network input
        a_lin = self._unscale(a[:, 0], LINEAR_MIN, LINEAR_MAX)
        a_ang = self._unscale(a[:, 1], ANGULAR_MIN, ANGULAR_MAX)
        a_norm = np.stack([a_lin, a_ang], axis=1)
        a_norm = torch.FloatTensor(a_norm).to(self.device)

        # ── Critic update ─────────────────────────────────────────────────────
        with torch.no_grad():
            # Target policy smoothing
            noise = (torch.randn_like(a_norm) * 0.2).clamp(-NOISE_CLIP, NOISE_CLIP)
            next_action = (self.actor_target(ns) + noise).clamp(-1.0, 1.0)

            # Clipped double Q-learning
            q1_target = self.critic1_target(ns, next_action)
            q2_target = self.critic2_target(ns, next_action)
            q_target  = torch.min(q1_target, q2_target).squeeze(1)
            target    = r + GAMMA * q_target * (1 - d)

        q1 = self.critic1(s, a_norm).squeeze(1)
        q2 = self.critic2(s, a_norm).squeeze(1)
        critic_loss = nn.MSELoss()(q1, target) + nn.MSELoss()(q2, target)

        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        nn.utils.clip_grad_norm_(self.critic1.parameters(), 1.0)
        nn.utils.clip_grad_norm_(self.critic2.parameters(), 1.0)
        self.critic_optimizer.step()

        result = {"critic_loss": critic_loss.item()}

        # ── Delayed actor update ──────────────────────────────────────────────
        self.updates += 1
        if self.updates % POLICY_DELAY == 0:
            actor_action = self.actor(s)
            actor_loss   = -self.critic1(s, actor_action).mean()

            self.actor_optimizer.zero_grad()
            actor_loss.backward()
            
            # Safety Check 5: Gradient Clipping to prevent policy explosion
            nn.utils.clip_grad_norm_(self.actor.parameters(), 1.0)
            
            self.actor_optimizer.step()
            nn.utils.clip_grad_norm_(self.actor.parameters(), 1.0)
            self.actor_optimizer.step()

            result["actor_loss"] = actor_loss.item()

            # Soft update all targets
            self._soft_update(self.actor, self.actor_target)
            self._soft_update(self.critic1, self.critic1_target)
            self._soft_update(self.critic2, self.critic2_target)

        return result

    def _soft_update(self, source: nn.Module, target: nn.Module):
        for p, tp in zip(source.parameters(), target.parameters()):
            tp.data.copy_(TAU * p.data + (1 - TAU) * tp.data)

    # ── persistence ───────────────────────────────────────────────────────────
    def save(self, path: str = "model_td3.pt"):
        torch.save({
            "actor": self.actor.state_dict(),
            "critic1": self.critic1.state_dict(),
            "critic2": self.critic2.state_dict(),
        }, path)
        print(f"TD3 model saved → {path}")

    def load(self, path: str = "model_td3.pt"):
        checkpoint = torch.load(path, map_location=self.device)
        self.actor.load_state_dict(checkpoint["actor"])
        self.critic1.load_state_dict(checkpoint["critic1"])
        self.critic2.load_state_dict(checkpoint["critic2"])
        self.actor_target.load_state_dict(self.actor.state_dict())
        self.critic1_target.load_state_dict(self.critic1.state_dict())
        self.critic2_target.load_state_dict(self.critic2.state_dict())
        print(f"TD3 model loaded ← {path}")
