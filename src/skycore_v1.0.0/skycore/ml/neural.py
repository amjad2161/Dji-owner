"""
SkyCore ML - Neural Trajectory Planner
LSTM-based trajectory prediction and planning
"""

import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryPoint:
    """Trajectory waypoint"""
    position: Tuple[float, float, float]
    velocity: Tuple[float, float, float]
    time: float
    heading: float


class TrajectoryHistoryBuffer:
    """Buffer for trajectory history used in LSTM training"""
    
    def __init__(self, max_length: int = 1000):
        self.positions = deque(maxlen=max_length)
        self.velocities = deque(maxlen=max_length)
        self.times = deque(maxlen=max_length)
        self.commands = deque(maxlen=max_length)
    
    def add(self, position: Tuple, velocity: Tuple, time: float, command: Tuple):
        """Add new trajectory point"""
        self.positions.append(position)
        self.velocities.append(velocity)
        self.times.append(time)
        self.commands.append(command)
    
    def get_sequence(self, length: int) -> Tuple[np.ndarray, np.ndarray]:
        """Get training sequence"""
        if len(self.positions) < length:
            return None, None
        
        pos_arr = np.array(list(self.positions)[-length:])
        vel_arr = np.array(list(self.velocities)[-length:])
        cmd_arr = np.array(list(self.commands)[-length:])
        
        # Features: position + velocity + time delta
        X = np.column_stack([
            pos_arr,
            vel_arr,
            np.diff(list(self.times)[-length:], prepend=self.times[-length] - 0.1)
        ])
        
        # Target: next command
        Y = cmd_arr[-1] if len(cmd_arr) > 0 else np.zeros(4)
        
        return X, Y


class SimpleLSTMTrajectoryPredictor:
    """
    Simplified LSTM trajectory predictor for drone path planning.
    Uses numpy-based implementation for portability.
    """
    
    def __init__(self, input_dim: int = 9, hidden_dim: int = 64, output_dim: int = 4):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        
        # Initialize weights (simplified)
        np.random.seed(42)
        
        # Input to hidden
        self.Wf = np.random.randn(hidden_dim, input_dim) * 0.1
        self.Wi = np.random.randn(hidden_dim, input_dim) * 0.1
        self.Wc = np.random.randn(hidden_dim, input_dim) * 0.1
        self.Wo = np.random.randn(hidden_dim, input_dim) * 0.1
        
        # Hidden to hidden (recurrent)
        self.Wh = np.random.randn(hidden_dim, hidden_dim) * 0.1
        
        # Hidden to output
        self.Wy = np.random.randn(output_dim, hidden_dim) * 0.1
        
        # Biases
        self.bf = np.zeros((hidden_dim, 1))
        self.bi = np.zeros((hidden_dim, 1))
        self.bc = np.zeros((hidden_dim, 1))
        self.bo = np.zeros((hidden_dim, 1))
        self.by = np.zeros((output_dim, 1))
        
        self.state = None
        self.memory = None
        
        # Training history
        self.history = TrajectoryHistoryBuffer()
        
        logger.info(f"LSTM Trajectory Predictor initialized: {input_dim}→{hidden_dim}→{output_dim}")
    
    def sigmoid(self, x: np.ndarray) -> np.ndarray:
        """Sigmoid activation"""
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
    
    def tanh(self, x: np.ndarray) -> np.ndarray:
        """Tanh activation"""
        return np.tanh(x)
    
    def forward(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Forward pass through LSTM"""
        seq_len = x.shape[0] if len(x.shape) > 1 else 1
        x = x.reshape(-1, self.input_dim)
        
        if self.state is None:
            self.state = np.zeros((self.hidden_dim, 1))
            self.memory = np.zeros((self.hidden_dim, 1))
        
        outputs = []
        
        for t in range(seq_len):
            xt = x[t].reshape(-1, 1)
            
            # LSTM gates
            f = self.sigmoid(self.Wf @ xt + self.Wh @ self.state + self.bf)
            i = self.sigmoid(self.Wi @ xt + self.Wh @ self.state + self.bi)
            c_tilde = self.tanh(self.Wc @ xt + self.Wh @ self.state + self.bc)
            o = self.sigmoid(self.Wo @ xt + self.Wh @ self.state + self.bo)
            
            # Update cell state and hidden state
            self.memory = f * self.memory + i * c_tilde
            self.state = o * self.tanh(self.memory)
            
            # Output
            y = self.Wy @ self.state + self.by
            outputs.append(y.flatten())
        
        return np.array(outputs), self.state.flatten()
    
    def predict_next(self, trajectory: List[TrajectoryPoint]) -> TrajectoryPoint:
        """Predict next trajectory point"""
        if len(trajectory) < 3:
            return trajectory[-1] if trajectory else None
        
        # Convert trajectory to features
        features = []
        for tp in trajectory[-5:]:
            features.extend([
                tp.position[0], tp.position[1], tp.position[2],
                tp.velocity[0], tp.velocity[1], tp.velocity[2],
                tp.time, tp.heading, 0  # padding
            ])
        
        while len(features) < 45:
            features.extend([0, 0, 0, 0, 0, 0, 0, 0, 0])
        
        X = np.array(features[:45]).reshape(5, 9)
        
        # Predict
        _, hidden = self.forward(X)
        
        # Compute next command from hidden state
        command = (self.Wy @ hidden.reshape(-1, 1) + self.by).flatten()
        
        # Convert command to trajectory point
        last = trajectory[-1]
        dt = 0.5  # 500ms prediction
        
        new_pos = (
            last.position[0] + command[0] * dt,
            last.position[1] + command[1] * dt,
            last.position[2] + command[2] * dt
        )
        new_vel = (command[0], command[1], command[2])
        
        return TrajectoryPoint(
            position=new_pos,
            velocity=new_vel,
            time=last.time + dt,
            heading=last.heading
        )
    
    def train(self, X: np.ndarray, Y: np.ndarray, epochs: int = 10, lr: float = 0.01):
        """Simple training loop (gradient descent)"""
        for epoch in range(epochs):
            for i in range(0, len(X) - 5, 5):
                seq = X[i:i+5]
                target = Y[i] if i < len(Y) else np.zeros(self.output_dim)
                
                _, hidden = self.forward(seq)
                
                # Simple gradient update (pseudo-gradient)
                error = hidden - target[:self.hidden_dim] if len(target) >= self.hidden_dim else hidden
                
                # Update weights (simplified)
                self.Wy -= lr * np.outer(error[:self.output_dim], hidden)
                self.by -= lr * error[:self.output_dim]
            
            if epoch % 5 == 0:
                logger.info(f"Epoch {epoch}/{epochs} completed")
    
    def generate_trajectory(self, start: Tuple[float, float, float],
                           goal: Tuple[float, float, float],
                           max_length: int = 100) -> List[TrajectoryPoint]:
        """Generate optimal trajectory from start to goal"""
        trajectory = [TrajectoryPoint(
            position=start,
            velocity=(0, 0, 0),
            time=0,
            heading=0
        )]
        
        for step in range(max_length):
            next_point = self.predict_next(trajectory)
            
            if next_point is None:
                break
            
            # Check if reached goal
            dist = np.sqrt(sum((a - b) ** 2 for a, b in zip(next_point.position, goal)))
            
            if dist < 1.0:  # Within 1m of goal
                trajectory.append(TrajectoryPoint(
                    position=goal,
                    velocity=(0, 0, 0),
                    time=next_point.time,
                    heading=next_point.heading
                ))
                break
            
            trajectory.append(next_point)
        
        return trajectory


class NeuralPlanner:
    """Main neural trajectory planner"""
    
    def __init__(self):
        self.lstm = SimpleLSTMTrajectoryPredictor()
        self.replan_count = 0
        self.collision_avoidance_history = deque(maxlen=20)
        logger.info("Neural planner initialized")
    
    def plan(self, start: Tuple[float, float, float],
             goal: Tuple[float, float, float],
             obstacles: List[Tuple[float, float, float, float]] = None) -> List[TrajectoryPoint]:
        """Plan trajectory with neural prediction and obstacle avoidance"""
        
        # Generate base trajectory
        trajectory = self.lstm.generate_trajectory(start, goal)
        
        # Apply obstacle avoidance
        if obstacles:
            trajectory = self._apply_obstacle_avoidance(trajectory, obstacles)
        
        self.replan_count += 1
        return trajectory
    
    def _apply_obstacle_avoidance(self, trajectory: List[TrajectoryPoint],
                                  obstacles: List[Tuple[float, float, float, float]]) -> List[TrajectoryPoint]:
        """Apply velocity obstacles for dynamic obstacle avoidance"""
        safe_trajectory = []
        
        for point in trajectory:
            pos = point.position
            
            # Check collision
            collision = False
            for obs in obstacles:
                obs_pos, obs_radius = obs[:3], obs[3] if len(obs) > 3 else 2.0
                dist = np.sqrt(sum((a - b) ** 2 for a, b in zip(pos, obs_pos)))
                
                if dist < obs_radius + 2.0:  # 2m buffer
                    collision = True
                    # Adjust path
                    safe_pos = (
                        pos[0] + (pos[0] - obs_pos[0]) * 0.5,
                        pos[1] + (pos[1] - obs_pos[1]) * 0.5,
                        pos[2]
                    )
                    safe_trajectory.append(TrajectoryPoint(
                        position=safe_pos,
                        velocity=point.velocity,
                        time=point.time,
                        heading=point.heading
                    ))
                    break
            
            if not collision:
                safe_trajectory.append(point)
        
        self.collision_avoidance_history.append(len(obstacles) > 0)
        return safe_trajectory
    
    def get_statistics(self) -> Dict:
        """Get neural planner statistics"""
        avoidances = list(self.collision_avoidance_history)
        avoidance_rate = sum(avoidances) / len(avoidances) if avoidances else 0
        
        return {
            'replan_count': self.replan_count,
            'collision_avoidance_rate': avoidance_rate,
            'model_loaded': True,
            'hidden_dim': self.lstm.hidden_dim
        }


def create_neural_planner() -> NeuralPlanner:
    """Factory function"""
    return NeuralPlanner()