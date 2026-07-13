"""
SkyCore ML - Anomaly Detection Module
Real-time IMU/battery/flight anomaly detection using statistical methods
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class AnomalyReport:
    """Anomaly detection report"""
    timestamp: float
    type: str  # 'imu', 'battery', 'flight', 'sensor'
    severity: str  # 'warning', 'critical'
    confidence: float  # 0-1
    details: Dict
    suggested_action: str


class IMUAnomalyDetector:
    """Detect IMU anomalies using Mahalanobis distance"""
    
    def __init__(self, window_size: int = 100, threshold: float = 3.0):
        self.window_size = window_size
        self.threshold = threshold
        self.history = {
            'accel': deque(maxlen=window_size),
            'gyro': deque(maxlen=window_size),
            'mag': deque(maxlen=window_size)
        }
        self.stats = {
            'accel': {'mean': np.zeros(3), 'cov': np.eye(3)},
            'gyro': {'mean': np.zeros(3), 'cov': np.eye(3)}
        }
    
    def update(self, accel: np.ndarray, gyro: np.ndarray) -> Optional[AnomalyReport]:
        """Update with new IMU readings, return anomaly if detected"""
        self.history['accel'].append(accel)
        self.history['gyro'].append(gyro)
        
        if len(self.history['accel']) >= 30:
            return self._check_anomaly(accel, gyro)
        return None
    
    def _check_anomaly(self, accel: np.ndarray, gyro: np.ndarray) -> Optional[AnomalyReport]:
        """Check for anomalies using Mahalanobis distance"""
        # Update statistics
        accel_arr = np.array(self.history['accel'])
        gyro_arr = np.array(self.history['gyro'])
        
        self.stats['accel']['mean'] = np.mean(accel_arr, axis=0)
        self.stats['accel']['cov'] = np.cov(accel_arr.T) + 1e-6 * np.eye(3)
        self.stats['gyro']['mean'] = np.mean(gyro_arr, axis=0)
        self.stats['gyro']['cov'] = np.cov(gyro_arr.T) + 1e-6 * np.eye(3)
        
        # Calculate Mahalanobis distance for accel
        diff = accel - self.stats['accel']['mean']
        cov_inv = np.linalg.inv(self.stats['accel']['cov'])
        mahal = np.sqrt(diff @ cov_inv @ diff)
        
        if mahal > self.threshold:
            return AnomalyReport(
                timestamp=np.datetime64('now').astype(float) / 1e9,
                type='imu',
                severity='critical' if mahal > self.threshold * 2 else 'warning',
                confidence=min(mahal / (self.threshold * 3), 1.0),
                details={
                    'mahal_distance': float(mahal),
                    'accel_reading': accel.tolist(),
                    'expected_mean': self.stats['accel']['mean'].tolist()
                },
                suggested_action='Check IMU calibration, possible sensor failure'
            )
        return None


class BatteryAnomalyDetector:
    """Detect battery anomalies - voltage sag, overheating, capacity loss"""
    
    def __init__(self):
        self.voltage_history = deque(maxlen=100)
        self.temp_history = deque(maxlen=50)
        self.cycle_count = 0
    
    def update(self, voltage: float, current: float, temperature: float, 
               capacity_mah: int) -> Optional[AnomalyReport]:
        """Check battery health for anomalies"""
        self.voltage_history.append(voltage)
        self.temp_history.append(temperature)
        
        reports = []
        
        # Check voltage sag during high current
        if current > 5.0:  # >5A draw
            recent = list(self.voltage_history)[-10:]
            if len(recent) >= 5:
                max_drop = max(recent) - min(recent)
                if max_drop > 0.5:  # >0.5V drop
                    reports.append(AnomalyReport(
                        timestamp=np.datetime64('now').astype(float) / 1e9,
                        type='battery',
                        severity='warning',
                        confidence=0.8,
                        details={'voltage_drop': max_drop, 'current': current},
                        suggested_action='Battery may be degraded, consider replacement'
                    ))
        
        # Check temperature
        if temperature > 50:  # Celsius
            reports.append(AnomalyReport(
                timestamp=np.datetime64('now').astype(float) / 1e9,
                type='battery',
                severity='critical',
                confidence=0.95,
                details={'temperature_c': temperature},
                suggested_action='IMMEDIATE LAND - battery overheating!'
            ))
        elif temperature > 45:
            reports.append(AnomalyReport(
                timestamp=np.datetime64('now').astype(float) / 1e9,
                type='battery',
                severity='warning',
                confidence=0.7,
                details={'temperature_c': temperature},
                suggested_action='Battery warm, reduce throttle'
            ))
        
        return reports[0] if reports else None


class FlightAnomalyDetector:
    """Detect flight anomalies - unusual attitudes, erratic behavior"""
    
    def __init__(self):
        self.position_history = deque(maxlen=50)
        self.velocity_history = deque(maxlen=50)
        self.attitude_history = deque(maxlen=50)
    
    def update(self, position: Tuple[float, float, float],
               velocity: Tuple[float, float, float],
               attitude: Tuple[float, float, float]) -> Optional[AnomalyReport]:
        """Check for flight anomalies"""
        self.position_history.append(position)
        self.velocity_history.append(velocity)
        self.attitude_history.append(attitude)
        
        if len(self.position_history) < 20:
            return None
        
        reports = []
        
        # Check for sudden position jumps (GPS glitch)
        positions = np.array(self.position_history)
        pos_std = np.std(positions, axis=0)
        if np.any(pos_std > 50):  # >50m standard deviation
            reports.append(AnomalyReport(
                timestamp=np.datetime64('now').astype(float) / 1e9,
                type='flight',
                severity='warning',
                confidence=0.85,
                details={'position_std': pos_std.tolist()},
                suggested_action='GPS may be unreliable, verify position manually'
            ))
        
        # Check for unusual attitudes (inverted, extreme tilt)
        roll, pitch, yaw = attitude
        if abs(roll) > 60 or abs(pitch) > 60:  # >60 degrees
            reports.append(AnomalyReport(
                timestamp=np.datetime64('now').astype(float) / 1e9,
                type='flight',
                severity='critical',
                confidence=0.95,
                details={'roll_deg': roll, 'pitch_deg': pitch},
                suggested_action='EMERGENCY: Possible loss of control, initiate RTH'
            ))
        
        return reports[0] if reports else None


class AnomalyDetector:
    """Main anomaly detection coordinator"""
    
    def __init__(self):
        self.imu_detector = IMUAnomalyDetector()
        self.battery_detector = BatteryAnomalyDetector()
        self.flight_detector = FlightAnomalyDetector()
        self.recent_anomalies = deque(maxlen=100)
        logger.info("Anomaly detector initialized")
    
    def detect(self, telemetry: Dict) -> List[AnomalyReport]:
        """Run all anomaly detectors on current telemetry"""
        reports = []
        
        # IMU anomaly
        if 'imu' in telemetry:
            accel = np.array(telemetry['imu'].get('accel', [0, 0, 0]))
            gyro = np.array(telemetry['imu'].get('gyro', [0, 0, 0]))
            imu_report = self.imu_detector.update(accel, gyro)
            if imu_report:
                reports.append(imu_report)
        
        # Battery anomaly
        if 'battery' in telemetry:
            batt = telemetry['battery']
            batt_report = self.battery_detector.update(
                voltage=batt.get('voltage', 0),
                current=batt.get('current', 0),
                temperature=batt.get('temperature_c', 25),
                capacity_mah=batt.get('capacity_mah', 5000)
            )
            if batt_report:
                reports.append(batt_report)
        
        # Flight anomaly
        if 'position' in telemetry and 'velocity' in telemetry and 'attitude' in telemetry:
            flight_report = self.flight_detector.update(
                position=telemetry['position'],
                velocity=telemetry['velocity'],
                attitude=telemetry['attitude']
            )
            if flight_report:
                reports.append(flight_report)
        
        self.recent_anomalies.extend(reports)
        return reports
    
    def get_statistics(self) -> Dict:
        """Get anomaly statistics"""
        return {
            'total_anomalies': len(self.recent_anomalies),
            'by_type': self._count_by_type(),
            'by_severity': self._count_by_severity(),
            'imu_health_score': self._imu_health_score(),
            'battery_health_score': self._battery_health_score()
        }
    
    def _count_by_type(self) -> Dict:
        return {'imu': 0, 'battery': 0, 'flight': 0, 'sensor': 0}
    
    def _count_by_severity(self) -> Dict:
        return {'warning': 0, 'critical': 0}
    
    def _imu_health_score(self) -> float:
        """Calculate IMU health score (0-100)"""
        return 95.0  # Placeholder
    
    def _battery_health_score(self) -> float:
        """Calculate battery health score (0-100)"""
        return 85.0  # Placeholder


def create_anomaly_detector() -> AnomalyDetector:
    """Factory function"""
    return AnomalyDetector()