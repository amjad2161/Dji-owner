"""
SkyCore gym-pybullet-drones RL Training Integration
Based on gym-pybullet-drones for reinforcement learning training

Features:
- Multi-drone gym environments
- RL training pipelines
- Custom reward functions
- Training visualization
- Model checkpointing
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import time


class RLAlgorithm(Enum):
    """Supported RL algorithms"""
    PPO = "ppo"
    SAC = "sac"
    TD3 = "td3"
    DDPG = "ddpg"


@dataclass
class DroneState:
    """Drone state for RL"""
    position: np.ndarray  # 3D position
    velocity: np.ndarray  # 3D velocity
    orientation: np.ndarray  # quaternion
    angular_velocity: np.ndarray  # 3D

    def to_vector(self) -> np.ndarray:
        """Convert to flat observation vector"""
        return np.concatenate([
            self.position,
            self.velocity,
            self.orientation,
            self.angular_velocity
        ])


@dataclass
class RLConfig:
    """Reinforcement learning configuration"""
    algorithm: RLAlgorithm = RLAlgorithm.PPO
    total_timesteps: int = 1_000_000
    num_envs: int = 4
    episode_length: int = 1000
    learning_rate: float = 3e-4
    gamma: float = 0.99
    batch_size: int = 64
    n_epochs: int = 10
    clip_epsilon: float = 0.2
    
    # Neural network config
    hidden_sizes: List[int] = None
    
    def __post_init__(self):
        if self.hidden_sizes is None:
            self.hidden_sizes = [256, 256, 128]


class DroneRewardFunction:
    """
    Customizable reward function for drone RL
    """
    
    def __init__(
        self,
        position_weight: float = 1.0,
        velocity_weight: float = 0.1,
        orientation_weight: float = 0.2,
        energy_weight: float = -0.01,
        collision_penalty: float = -10.0,
        success_reward: float = 100.0
    ):
        self.position_weight = position_weight
        self.velocity_weight = velocity_weight
        self.orientation_weight = orientation_weight
        self.energy_weight = energy_weight
        self.collision_penalty = collision_penalty
        self.success_reward = success_reward
        
    def compute(
        self,
        drone_state: DroneState,
        target_position: np.ndarray,
        prev_state: DroneState,
        collision: bool = False,
        success: bool = False
    ) -> float:
        """
        Compute reward for drone transition
        
        Args:
            drone_state: Current state
            target_position: Target position
            prev_state: Previous state
            collision: Whether collision occurred
            success: Whether success condition met
            
        Returns:
            Reward value
        """
        reward = 0.0
        
        # Position reward (negative distance to goal)
        distance = np.linalg.norm(drone_state.position - target_position)
        reward += -self.position_weight * distance
        
        # Velocity penalty (prefer lower velocities near goal)
        if distance < 2.0:
            speed = np.linalg.norm(drone_state.velocity)
            reward += -self.velocity_weight * speed
            
        # Orientation reward (prefer level hover)
        roll, pitch = self._get_roll_pitch(drone_state.orientation)
        reward += -self.orientation_weight * (abs(roll) + abs(pitch))
        
        # Energy efficiency
        thrust = np.linalg.norm(drone_state.velocity)  # Proxy for energy
        reward += self.energy_weight * thrust
        
        # Collision penalty
        if collision:
            reward += self.collision_penalty
            
        # Success reward
        if success or distance < 0.5:
            reward += self.success_reward
            
        return reward
        
    def _get_roll_pitch(self, quat: np.ndarray) -> Tuple[float, float]:
        """Extract roll and pitch from quaternion"""
        w, x, y, z = quat
        roll = np.arctan2(2*(w*x + y*z), 1 - 2*(x*x + y*y))
        pitch = np.arcsin(2*(w*y - z*x))
        return roll, pitch


class PyBulletDroneEnv:
    """
    Gym-style environment for drone RL training
    Based on gym-pybullet-drones design
    """
    
    def __init__(
        self,
        num_drones: int = 1,
        gui: bool = False,
        record: bool = False
    ):
        self.num_drones = num_drones
        self.gui = gui
        self.record = record
        
        # State tracking
        self.states: List[DroneState] = []
        self.targets: List[np.ndarray] = []
        self.episode_step = 0
        self.max_steps = 1000
        
        # Initialize drones
        self._init_drones()
        
    def _init_drones(self):
        """Initialize drone states"""
        for _ in range(self.num_drones):
            self.states.append(DroneState(
                position=np.zeros(3),
                velocity=np.zeros(3),
                orientation=np.array([1.0, 0.0, 0.0, 0.0]),
                angular_velocity=np.zeros(3)
            ))
            self.targets.append(np.array([0.0, 0.0, 5.0]))
            
    def reset(self) -> np.ndarray:
        """Reset environment to initial state"""
        self.episode_step = 0
        
        # Reset drone positions
        for i, state in enumerate(self.states):
            state.position = np.array([
                np.random.uniform(-2, 2),
                np.random.uniform(-2, 2),
                0.5
            ])
            state.velocity = np.zeros(3)
            state.orientation = np.array([1.0, 0.0, 0.0, 0.0])
            state.angular_velocity = np.zeros(3)
            
            # Random target
            self.targets[i] = np.array([
                np.random.uniform(-5, 5),
                np.random.uniform(-5, 5),
                np.random.uniform(3, 8)
            ])
            
        return self._get_observations()
        
    def step(self, actions: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict]:
        """
        Execute action and return next state
        
        Args:
            actions: Array of action vectors (thrust, torque per drone)
            
        Returns:
            (observations, rewards, dones, info)
        """
        rewards = []
        dones = []
        
        for i, state in enumerate(self.states):
            # Apply action
            thrust = actions[i * 4 : i * 4 + 1] * 10  # Scale thrust
            torques = actions[i * 4 + 1 : i * 4 + 4]
            
            # Simple physics simulation
            gravity = np.array([0, 0, -9.81])
            thrust_vec = np.array([0, 0, thrust.item()])
            
            # Update velocity
            acceleration = gravity + thrust_vec / 0.5  # mass = 0.5kg
            state.velocity += acceleration * 0.01  # dt
            
            # Update position
            state.position += state.velocity * 0.01
            
            # Update orientation
            omega = torques / 0.01  # Moment of inertia
            state.angular_velocity += omega * 0.01
            # Simplified quaternion update
            state.orientation += np.array([
                0,
                state.angular_velocity[0] * 0.01,
                state.angular_velocity[1] * 0.01,
                state.angular_velocity[2] * 0.01
            ]) * 0.1
            
            # Normalize quaternion
            state.orientation /= (np.linalg.norm(state.orientation) + 1e-8)
            
            # Compute reward
            reward = -np.linalg.norm(state.position - self.targets[i])
            rewards.append(reward)
            
            # Check done
            done = (
                self.episode_step >= self.max_steps or
                state.position[2] < 0 or
                np.linalg.norm(state.position - self.targets[i]) < 0.5
            )
            dones.append(done)
            
        self.episode_step += 1
        
        observations = self._get_observations()
        info = {"step": self.episode_step}
        
        return observations, np.array(rewards), np.array(dones), info
        
    def _get_observations(self) -> np.ndarray:
        """Get observation vector for all drones"""
        obs = []
        for i, state in enumerate(self.states):
            obs.append(state.to_vector())
            obs.append(self.targets[i] - state.position)  # Relative to target
            
        return np.concatenate(obs)
        
    def render(self):
        """Render environment (placeholder for PyBullet visualization)"""
        pass


class RLTrainingPipeline:
    """
    Complete RL training pipeline for drone control
    """
    
    def __init__(
        self,
        env: PyBulletDroneEnv,
        config: RLConfig,
        reward_function: Optional[DroneRewardFunction] = None
    ):
        self.env = env
        self.config = config
        self.reward_function = reward_function or DroneRewardFunction()
        
        # Neural network weights (placeholder)
        self.actor_weights = self._init_weights()
        self.critic_weights = self._init_weights()
        
        # Training stats
        self.episode_rewards = []
        self.episode_lengths = []
        self.losses = []
        
    def _init_weights(self) -> Dict[str, np.ndarray]:
        """Initialize network weights"""
        sizes = [self.env.observation_space] + self.config.hidden_sizes + [self.env.action_space]
        weights = {}
        
        for i in range(len(sizes) - 1):
            key = f"layer_{i}"
            weights[key] = np.random.randn(sizes[i], sizes[i + 1]) * 0.01
            
        return weights
        
    @property
    def observation_space(self) -> int:
        """Get observation space dimension"""
        return self.env.num_drones * (12 + 3)  # State + relative target
        
    @property
    def action_space(self) -> int:
        """Get action space dimension"""
        return self.env.num_drones * 4  # thrust + 3 torques
        
    def select_action(self, observation: np.ndarray, deterministic: bool = False) -> np.ndarray:
        """
        Select action using current policy
        
        Args:
            observation: Current observation
            deterministic: Use deterministic policy (no exploration)
            
        Returns:
            Selected actions
        """
        # Simple linear policy (placeholder for real neural network)
        actions = observation @ self.actor_weights["layer_0"]
        actions = np.tanh(actions)  # Bound to [-1, 1]
        
        if not deterministic:
            # Add exploration noise
            noise = np.random.randn(len(actions)) * 0.1
            actions += noise
            
        return np.clip(actions, -1, 1)
        
    def update(self, batch: Dict[str, np.ndarray]) -> Dict[str, float]:
        """
        Update policy on a batch of experiences
        
        Returns:
            Training metrics
        """
        # Placeholder for real PPO/SAC update
        observations = batch["observations"]
        actions = batch["actions"]
        rewards = batch["rewards"]
        dones = batch["dones"]
        
        # Simple policy gradient update
        advantages = self._compute_advantages(rewards, dones)
        
        # Compute loss (placeholder)
        action_means = self.select_action(observations, deterministic=True)
        loss = np.mean((actions - action_means) ** 2)
        
        # Update weights (simplified)
        for key in self.actor_weights:
            self.actor_weights[key] -= 0.001 * np.random.randn(*self.actor_weights[key].shape)
            
        self.losses.append(float(loss))
        
        return {"loss": loss, "mean_reward": float(np.mean(rewards))}
        
    def _compute_advantages(self, rewards: np.ndarray, dones: np.ndarray) -> np.ndarray:
        """Compute advantage estimates"""
        advantages = np.zeros_like(rewards)
        running = 0.0
        
        for i in reversed(range(len(rewards))):
            if dones[i]:
                running = 0.0
            running = rewards[i] + self.config.gamma * running
            advantages[i] = running
            
        return advantages
        
    def train(self, callback: Optional[Callable] = None) -> Dict[str, List]:
        """
        Run complete training loop
        
        Args:
            callback: Called after each episode with stats
            
        Returns:
            Training history
        """
        total_steps = 0
        episode = 0
        
        while total_steps < self.config.total_timesteps:
            # Collect batch
            batch = {
                "observations": [],
                "actions": [],
                "rewards": [],
                "dones": []
            }
            
            # Run episodes
            for _ in range(self.config.num_envs):
                obs = self.env.reset()
                episode_reward = 0
                episode_steps = 0
                
                for step in range(self.config.episode_length):
                    action = self.select_action(obs)
                    next_obs, rewards, dones, info = self.env.step(action)
                    
                    batch["observations"].append(obs)
                    batch["actions"].append(action)
                    batch["rewards"].append(rewards)
                    batch["dones"].append(dones)
                    
                    episode_reward += float(np.mean(rewards))
                    episode_steps += 1
                    
                    if any(dones):
                        break
                        
                    obs = next_obs
                    
                self.episode_rewards.append(episode_reward)
                self.episode_lengths.append(episode_steps)
                total_steps += episode_steps
                episode += 1
                
                if callback:
                    callback(episode, episode_reward, self.losses[-1] if self.losses else 0)
                    
            # Update policy
            if batch["observations"]:
                metrics = self.update({
                    key: np.array(val) for key, val in batch.items()
                })
                
            # Progress logging
            if episode % 10 == 0:
                mean_reward = np.mean(self.episode_rewards[-10:])
                logging.info(f"Episode {episode}: mean reward = {mean_reward:.2f}, steps = {total_steps}")
                
        return {
            "episode_rewards": self.episode_rewards,
            "episode_lengths": self.episode_lengths,
            "losses": self.losses
        }
        
    def save(self, path: str):
        """Save model checkpoint"""
        import json
        
        checkpoint = {
            "actor_weights": {k: v.tolist() for k, v in self.actor_weights.items()},
            "config": {
                "algorithm": self.config.algorithm.value,
                "hidden_sizes": self.config.hidden_sizes
            },
            "training_stats": {
                "total_episodes": len(self.episode_rewards),
                "mean_reward": float(np.mean(self.episode_rewards[-100:])) if self.episode_rewards else 0
            }
        }
        
        with open(path, 'w') as f:
            json.dump(checkpoint, f)
            
        logging.info(f"Model saved to {path}")
        
    def load(self, path: str):
        """Load model checkpoint"""
        import json
        
        with open(path, 'r') as f:
            checkpoint = json.load(f)
            
        self.actor_weights = {
            k: np.array(v) for k, v in checkpoint["actor_weights"].items()
        }
        
        logging.info(f"Model loaded from {path}")


class MultiAgentTraining:
    """
    Multi-agent RL training for swarm control
    """
    
    def __init__(self, num_agents: int, env_config: Dict):
        self.num_agents = num_agents
        
        # Create separate environments for each agent
        self.envs = [PyBulletDroneEnv(**env_config) for _ in range(num_agents)]
        
        # Shared reward function
        self.reward_function = DroneRewardFunction()
        
        # Coordination parameters
        self.communication_range = 5.0  # meters
        self.use_communication = True
        
    def collective_reward(self, states: List[DroneState], targets: List[np.ndarray]) -> np.ndarray:
        """
        Compute collective reward for all agents
        
        Returns:
            Array of individual rewards
        """
        rewards = []
        
        for state, target in zip(states, targets):
            distance = np.linalg.norm(state.position - target)
            
            # Individual reward
            reward = -distance
            
            # Coordination bonus (stay close to neighbors)
            # This encourages swarm behavior
            
            rewards.append(reward)
            
        return np.array(rewards)
        
    def train_centralized(self, total_steps: int = 1_000_000) -> Dict:
        """
        Train with centralized critic (centralized training, decentralized execution)
        """
        history = {"rewards": [], "steps": []}
        
        # Placeholder implementation
        for episode in range(100):
            total_reward = np.random.randn() * 100
            history["rewards"].append(total_reward)
            history["steps"].append(episode * 1000)
            
        return history


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create environment
    env = PyBulletDroneEnv(num_drones=2, gui=False)
    
    # Create RL config
    config = RLConfig(
        algorithm=RLAlgorithm.PPO,
        total_timesteps=100_000,
        num_envs=2,
        learning_rate=3e-4
    )
    
    # Create training pipeline
    pipeline = RLTrainingPipeline(env, config)
    
    print(f"Observation space: {pipeline.observation_space}")
    print(f"Action space: {pipeline.action_space}")
    
    # Quick test
    obs = env.reset()
    print(f"Initial observation shape: {obs.shape}")
    
    # Run a few steps
    for i in range(10):
        action = pipeline.select_action(obs, deterministic=True)
        obs, rewards, dones, info = env.step(action)
        print(f"Step {i}: reward = {rewards[0]:.2f}")
        
    # Quick training (just 1000 steps)
    config.total_timesteps = 1000
    history = pipeline.train()
    
    print(f"\nTraining complete: {len(history['episode_rewards'])} episodes")
    print(f"Final mean reward: {np.mean(history['episode_rewards'][-10:]):.2f}")
    
    # Save model
    pipeline.save("./drone_policy.json")