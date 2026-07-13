"""
SkyCore Strapdown Inertial Navigation System (INS)
==================================================
Dead reckoning using IMU data.
"""

import numpy as np
from typing import Dict, Tuple, Optional
import math
import logging

log = logging.getLogger(__name__)


class StrapdownINS:
    """
    Strapdown INS for dead reckoning.
    
    Integrates IMU data to estimate position and velocity.
    Used when GPS is unavailable.
    """
    
    def __init__(self, gravity: float = 9.81):
        """
        Initialize INS.
        
        Args:
            gravity: Gravity magnitude (m/s^2)
        """
        self.g = gravity
        
        # State
        self.lat = 0.0      # Latitude (rad)
        self.lon = 0.0      # Longitude (rad)
        self.alt = 0.0      # Altitude (m)
        
        self.vn = 0.0       # North velocity (m/s)
        self.ve = 0.0       # East velocity (m/s)
        self.vd = 0.0       # Down velocity (m/s)
        
        # Euler angles
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        
        # Quaternion
        self.q = np.array([1.0, 0.0, 0.0, 0.0])
        
        # Initial position
        self.initial_lat = 0.0
        self.initial_lon = 0.0
        self.initial_alt = 0.0
        
        # IMU biases
        self.gyro_bias = np.zeros(3)
        self.accel_bias = np.zeros(3)
        
        # Earth parameters (WGS84)
        self.R_e = 6378137.0  # Semi-major axis
        self.f = 1/298.257223563  # Flattening
        self.e2 = 2*self.f - self.f*self.f
        
        self.initialized = False
    
    def initialize(self, lat: float, lon: float, alt: float,
                   roll: float = 0, pitch: float = 0, yaw: float = 0):
        """
        Initialize INS with starting position and attitude.
        
        Args:
            lat: Latitude (deg)
            lon: Longitude (deg)
            alt: Altitude (m)
            roll, pitch, yaw: Initial attitude (deg)
        """
        self.lat = math.radians(lat)
        self.lon = math.radians(lon)
        self.alt = alt
        
        self.initial_lat = self.lat
        self.initial_lon = self.lon
        self.initial_alt = self.alt
        
        self.roll = math.radians(roll)
        self.pitch = math.radians(pitch)
        self.yaw = math.radians(yaw)
        
        # Quaternion from Euler
        self.q = self._euler_to_quaternion(self.roll, self.pitch, self.yaw)
        
        self.initialized = True
        log.info(f"INS initialized at {lat:.6f}, {lon:.6f}, {alt:.1f}m")
    
    def update(self, accel: np.ndarray, gyro: np.ndarray, dt: float) -> Dict:
        """
        Update INS with IMU data.
        
        Args:
            accel: Accelerometer reading [ax, ay, az] (m/s^2)
            gyro: Gyroscope reading [gx, gy, gz] (rad/s)
            dt: Time step (s)
            
        Returns:
            State dictionary
        """
        if not self.initialized:
            log.warning("INS not initialized")
            return {}
        
        # Remove biases
        accel_corrected = accel - self.accel_bias
        gyro_corrected = gyro - self.gyro_bias
        
        # Update attitude (quaternion integration)
        self._update_attitude(gyro_corrected, dt)
        
        # Extract DCM (Direction Cosine Matrix)
        C_bn = self._quaternion_to_dcm(self.q)
        
        # Transform body-frame acceleration to navigation frame
        accel_n = C_bn @ accel_corrected
        
        # Remove gravity
        f_n = np.array([accel_n[0], accel_n[1], accel_n[2] - self.g])
        f_e = np.array([accel_n[0], accel_n[1], accel_n[2] + self.g])
        
        # Compute navigation-frame acceleration
        # Include Coriolis and centripetal terms
        omega_ie = 7.292115e-5  # Earth rotation rate (rad/s)
        
        # Coriolis acceleration
        coriolis = np.array([
            2*omega_ie*self.ve*math.sin(self.lat) + self.vn*self.ve*math.sin(2*self.lat)/(self.R_e + self.alt),
            -2*omega_ie*self.vn*math.sin(self.lat) - (self.vn**2 - self.ve**2)*math.sin(2*self.lat)/(self.R_e + self.alt),
            (self.vn**2 + self.ve**2)*math.cos(self.lat)/(self.R_e + self.alt)
        ])
        
        # Update velocity
        self.vn += (f_n[0] - coriolis[0]) * dt
        self.ve += (f_n[1] - coriolis[1]) * dt
        self.vd += (f_e[2] - coriolis[2]) * dt
        
        # Update position
        self._update_position(dt)
        
        return self.get_state()
    
    def _update_attitude(self, gyro: np.ndarray, dt: float):
        """Update attitude quaternion."""
        # Quaternion derivative
        omega = np.array([0, gyro[0], gyro[1], gyro[2]])
        q_dot = 0.5 * self._quaternion_multiply(self.q, omega)
        
        # Integrate
        self.q += q_dot * dt
        
        # Normalize
        self.q /= np.linalg.norm(self.q)
    
    def _update_position(self, dt: float):
        """Update position using velocity."""
        # Meridian radius of curvature
        R_M = self.R_e * (1 - self.e2) / (1 - self.e2*math.sin(self.lat)**2)**1.5
        
        # Prime vertical radius of curvature
        R_N = self.R_e / math.sqrt(1 - self.e2*math.sin(self.lat)**2)
        
        # Update latitude
        self.lat += self.vn / R_M * dt
        
        # Update longitude
        self.lon += self.ve / (R_N * math.cos(self.lat)) * dt
        
        # Update altitude
        self.alt -= self.vd * dt
    
    def _euler_to_quaternion(self, roll: float, pitch: float, yaw: float) -> np.ndarray:
        """Convert Euler angles to quaternion."""
        cr = math.cos(roll / 2)
        sr = math.sin(roll / 2)
        cp = math.cos(pitch / 2)
        sp = math.sin(pitch / 2)
        cy = math.cos(yaw / 2)
        sy = math.sin(yaw / 2)
        
        return np.array([
            cr * cp * cy + sr * sp * sy,
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy
        ])
    
    def _quaternion_to_dcm(self, q: np.ndarray) -> np.ndarray:
        """Convert quaternion to Direction Cosine Matrix."""
        q0, q1, q2, q3 = q
        
        C = np.zeros((3, 3))
        C[0, 0] = q0**2 + q1**2 - q2**2 - q3**2
        C[0, 1] = 2*(q1*q2 - q0*q3)
        C[0, 2] = 2*(q1*q3 + q0*q2)
        C[1, 0] = 2*(q1*q2 + q0*q3)
        C[1, 1] = q0**2 - q1**2 + q2**2 - q3**2
        C[1, 2] = 2*(q2*q3 - q0*q1)
        C[2, 0] = 2*(q1*q3 - q0*q2)
        C[2, 1] = 2*(q2*q3 + q0*q1)
        C[2, 2] = q0**2 - q1**2 - q2**2 + q3**2
        
        return C
    
    def _quaternion_multiply(self, q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Multiply two quaternions."""
        result = np.zeros(4)
        result[0] = q1[0]*q2[0] - q1[1]*q2[1] - q1[2]*q2[2] - q1[3]*q2[3]
        result[1] = q1[0]*q2[1] + q1[1]*q2[0] + q1[2]*q2[3] - q1[3]*q2[2]
        result[2] = q1[0]*q2[2] - q1[1]*q2[3] + q1[2]*q2[0] + q1[3]*q2[1]
        result[3] = q1[0]*q2[3] + q1[1]*q2[2] - q1[2]*q2[1] + q1[3]*q2[0]
        return result
    
    def get_euler(self) -> Tuple[float, float, float]:
        """Get Euler angles in degrees."""
        roll = math.atan2(2*(self.q[0]*self.q[1] + self.q[2]*self.q[3]),
                          1 - 2*(self.q[1]**2 + self.q[2]**2))
        pitch = math.asin(2*(self.q[0]*self.q[2] - self.q[3]*self.q[1]))
        yaw = math.atan2(2*(self.q[0]*self.q[3] + self.q[1]*self.q[2]),
                        1 - 2*(self.q[2]**2 + self.q[3]**2))
        
        return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)
    
    def get_state(self) -> Dict:
        """Get current INS state."""
        roll, pitch, yaw = self.get_euler()
        
        return {
            'position': {
                'lat': math.degrees(self.lat),
                'lon': math.degrees(self.lon),
                'alt': self.alt
            },
            'velocity': {
                'vn': self.vn,
                've': self.ve,
                'vd': self.vd,
                'speed': math.sqrt(self.vn**2 + self.ve**2)
            },
            'attitude': {
                'roll': roll,
                'pitch': pitch,
                'yaw': yaw
            },
            'quaternion': self.q.tolist(),
            'gyro_bias': self.gyro_bias.tolist(),
            'accel_bias': self.accel_bias.tolist()
        }
    
    def reset(self, lat: float, lon: float, alt: float):
        """Reset INS to new position."""
        self.vn = 0
        self.ve = 0
        self.vd = 0
        self.q = np.array([1, 0, 0, 0])
        self.initialize(lat, lon, alt)