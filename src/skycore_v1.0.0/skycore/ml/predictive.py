"""
SkyCore ML - Predictive Maintenance Module
Predictive failure models for drone components
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class MaintenancePrediction:
    """Maintenance prediction report"""
    component: str
    estimated_failure_date: datetime
    confidence: float
    health_score: float  # 0-100
    indicators: List[str]
    recommended_action: str


class BatteryHealthPredictor:
    """Predict battery remaining life and failure risk"""
    
    def __init__(self, nominal_capacity_mah: int = 5000):
        self.nominal_capacity = nominal_capacity_mah
        self.cycle_count = 0
        self.capacity_history = deque(maxlen=50)
        self.voltage_profile_history = deque(maxlen=100)
        self.temp_history = deque(maxlen=200)
        self.charge_history = deque(maxlen=50)
    
    def update(self, charged_mah: int, start_percent: float, end_percent: float,
               min_voltage: float, max_temp_c: float, date: datetime):
        """Update battery usage history"""
        self.cycle_count += 1
        
        # Calculate actual capacity used
        actual_capacity = charged_mah if charged_mah > 0 else (
            self.nominal_capacity * (start_percent - end_percent) / 100
        )
        self.capacity_history.append(actual_capacity)
        self.voltage_profile_history.append(min_voltage)
        self.temp_history.append(max_temp_c)
        self.charge_history.append({
            'date': date,
            'charged_mah': charged_mah,
            'start': start_percent,
            'end': end_percent
        })
    
    def predict_health(self) -> MaintenancePrediction:
        """Predict battery health and remaining life"""
        if len(self.capacity_history) < 5:
            return MaintenancePrediction(
                component='battery',
                estimated_failure_date=datetime.now() + timedelta(days=365),
                confidence=0.3,
                health_score=100.0,
                indicators=['Insufficient data for prediction'],
                recommended_action='Continue normal monitoring'
            )
        
        # Calculate degradation rate
        recent = list(self.capacity_history)[-10:]
        degradation_rate = (max(recent) - min(recent)) / len(recent)
        
        # Estimate current capacity
        avg_capacity = np.mean(list(self.capacity_history)[-5:])
        health_score = (avg_capacity / self.nominal_capacity) * 100
        health_score = max(0, min(100, health_score))
        
        # Check temperature issues
        temps = list(self.temp_history)
        high_temp_count = sum(1 for t in temps if t > 45)
        temp_factor = 1 - (high_temp_count / len(temps)) * 0.3 if temps else 1.0
        health_score *= temp_factor
        
        # Check voltage sag
        voltages = list(self.voltage_profile_history)
        if len(voltages) >= 5:
            recent_voltages = voltages[-5:]
            if min(recent_voltages) < 3.5:  # Per cell
                health_score *= 0.8
        
        # Calculate remaining cycles
        if degradation_rate > 0:
            remaining_capacity = self.nominal_capacity * 0.7  # 70% EOL
            remaining_cycles = (avg_capacity - remaining_capacity) / degradation_rate
        else:
            remaining_cycles = 50  # Assume good battery
        
        days_remaining = remaining_cycles * 0.5  # Average flight per week
        failure_date = datetime.now() + timedelta(days=max(0, days_remaining))
        
        # Determine indicators
        indicators = []
        if health_score < 60:
            indicators.append('⚠️ Capacity below 60%')
        if high_temp_count > len(temps) * 0.1:
            indicators.append('⚠️ Frequent high temperatures')
        if degradation_rate > 5:
            indicators.append('⚠️ Rapid capacity degradation')
        if min(voltages) < 3.4 if voltages else False:
            indicators.append('⚠️ Low voltage sag detected')
        
        confidence = min(0.9, len(self.capacity_history) / 50 + 0.1)
        
        return MaintenancePrediction(
            component='battery',
            estimated_failure_date=failure_date,
            confidence=confidence,
            health_score=health_score,
            indicators=indications if indicators else ['✅ Battery healthy'],
            recommended_action='Replace within 30 days' if health_score < 50 else 'Continue monitoring'
        )


class ESCHealthPredictor:
    """Predict ESC health from motor current signatures"""
    
    def __init__(self, num_motors: int = 4):
        self.num_motors = num_motors
        self.current_profiles = [deque(maxlen=100) for _ in range(num_motors)]
        self.temp_profiles = [deque(maxlen=50) for _ in range(num_motors)]
        self.vibration_levels = [deque(maxlen=50) for _ in range(num_motors)]
    
    def update(self, motor_currents: List[float], motor_temps: List[float],
               vibration: List[float]):
        """Update ESC telemetry"""
        for i, current in enumerate(motor_currents[:self.num_motors]):
            self.current_profiles[i].append(current)
        for i, temp in enumerate(motor_temps[:self.num_motors]):
            self.temp_profiles[i].append(temp)
        for i, vib in enumerate(vibration[:self.num_motors]):
            self.vibration_levels[i].append(vib)
    
    def predict_health(self) -> List[MaintenancePrediction]:
        """Predict health for each ESC"""
        predictions = []
        
        for motor_idx in range(self.num_motors):
            health_score = 100.0
            indicators = []
            
            # Check current imbalance
            currents = list(self.current_profiles[motor_idx])
            if len(currents) >= 10:
                avg_current = np.mean(currents[-10:])
                std_current = np.std(currents[-10:])
                
                # Check for abnormal draw
                if avg_current > 15:  # High current
                    health_score -= 20
                    indicators.append('High average current draw')
                if std_current > 5:  # Unstable current
                    health_score -= 15
                    indicators.append('Unstable current pattern')
            
            # Check temperature
            temps = list(self.temp_profiles[motor_idx])
            if temps:
                max_temp = max(temps)
                if max_temp > 80:
                    health_score -= 30
                    indicators.append(f'High temperature: {max_temp}°C')
                elif max_temp > 60:
                    health_score -= 10
            
            # Check vibration
            vibrations = list(self.vibration_levels[motor_idx])
            if len(vibrations) >= 10:
                avg_vib = np.mean(vibrations[-10:])
                if avg_vib > 5.0:  # High vibration
                    health_score -= 20
                    indicators.append('Abnormal motor vibration')
            
            health_score = max(0, min(100, health_score))
            
            days_remaining = health_score * 2  # Rough estimate
            failure_date = datetime.now() + timedelta(days=days_remaining)
            
            predictions.append(MaintenancePrediction(
                component=f'ESC_motor_{motor_idx + 1}',
                estimated_failure_date=failure_date,
                confidence=0.7,
                health_score=health_score,
                indicators=indications if indicators else ['✅ Healthy'],
                recommended_action='Replace' if health_score < 50 else 'Continue monitoring'
            ))
        
        return predictions


class MotorHealthPredictor:
    """Predict brushless motor health"""
    
    def __init__(self, num_motors: int = 4):
        self.num_motors = num_motors
        self.rpm_history = [deque(maxlen=100) for _ in range(num_motors)]
        self.power_history = [deque(maxlen=100) for _ in range(num_motors)]
        self.efficiency_history = [deque(maxlen=50) for _ in range(num_motors)]
    
    def update(self, rpm: List[float], power: List[float]):
        """Update motor telemetry"""
        for i in range(min(len(rpm), self.num_motors)):
            self.rpm_history[i].append(rpm[i])
            self.power_history[i].append(power[i])
            
            if rpm[i] > 0 and power[i] > 0:
                efficiency = rpm[i] / power[i]
                self.efficiency_history[i].append(efficiency)
    
    def predict_health(self) -> List[MaintenancePrediction]:
        """Predict motor health"""
        predictions = []
        
        for motor_idx in range(self.num_motors):
            efficiency = list(self.efficiency_history[motor_idx])
            
            if len(efficiency) < 10:
                predictions.append(MaintenancePrediction(
                    component=f'motor_{motor_idx + 1}',
                    estimated_failure_date=datetime.now() + timedelta(days=180),
                    confidence=0.5,
                    health_score=100.0,
                    indicators=['Insufficient data'],
                    recommended_action='Continue monitoring'
                ))
                continue
            
            # Calculate efficiency degradation
            recent = efficiency[-5:]
            baseline = np.mean(efficiency[:10]) if len(efficiency) > 10 else np.mean(efficiency)
            current = np.mean(recent)
            
            efficiency_ratio = current / baseline if baseline > 0 else 1.0
            health_score = efficiency_ratio * 100
            health_score = max(0, min(100, health_score))
            
            indicators = []
            if efficiency_ratio < 0.8:
                indicators.append('⚠️ Efficiency degraded >20%')
            if efficiency_ratio < 0.6:
                indicators.append('🔴 Critical efficiency loss')
            
            days_remaining = health_score * 2
            failure_date = datetime.now() + timedelta(days=days_remaining)
            
            predictions.append(MaintenancePrediction(
                component=f'motor_{motor_idx + 1}',
                estimated_failure_date=failure_date,
                confidence=0.75,
                health_score=health_score,
                indicators=indications if indicators else ['✅ Motor healthy'],
                recommended_action='Inspect for debris' if health_score < 70 else 'Continue monitoring'
            ))
        
        return predictions


class PredictiveMaintenanceSystem:
    """Main predictive maintenance coordinator"""
    
    def __init__(self, num_motors: int = 4, battery_capacity: int = 5000):
        self.battery_predictor = BatteryHealthPredictor(battery_capacity)
        self.esc_predictor = ESCHealthPredictor(num_motors)
        self.motor_predictor = MotorHealthPredictor(num_motors)
        self.all_predictions = deque(maxlen=100)
        logger.info(f"Predictive maintenance initialized for {num_motors}-motor system")
    
    def update_telemetry(self, telemetry: Dict):
        """Update with new telemetry"""
        # Battery update
        if 'battery' in telemetry:
            batt = telemetry['battery']
            self.battery_predictor.update(
                charged_mah=batt.get('charged_mah', 0),
                start_percent=batt.get('start_percent', 0),
                end_percent=batt.get('percent', 0),
                min_voltage=batt.get('min_voltage_v', 3.8),
                max_temp_c=batt.get('max_temp_c', 30),
                date=datetime.now()
            )
        
        # ESC/Motor update
        if 'motors' in telemetry:
            motors = telemetry['motors']
            if 'current' in motors:
                self.esc_predictor.update(
                    motor_currents=motors['current'],
                    motor_temps=motors.get('temp', [30] * 4),
                    vibration=motors.get('vibration', [0] * 4)
                )
            if 'rpm' in motors:
                self.motor_predictor.update(
                    rpm=motors['rpm'],
                    power=motors.get('power', [0] * 4)
                )
    
    def get_predictions(self) -> List[MaintenancePrediction]:
        """Get all current predictions"""
        predictions = []
        
        predictions.append(self.battery_predictor.predict_health())
        predictions.extend(self.esc_predictor.predict_health())
        predictions.extend(self.motor_predictor.predict_health())
        
        self.all_predictions.extend(predictions)
        return predictions
    
    def get_next_maintenance(self) -> MaintenancePrediction:
        """Get the most urgent maintenance item"""
        predictions = self.get_predictions()
        
        # Sort by failure date and health score
        urgent = sorted(predictions, key=lambda p: (
            p.estimated_failure_date, -p.health_score
        ))
        
        return urgent[0] if urgent else None
    
    def get_fleet_summary(self) -> Dict:
        """Get fleet-wide maintenance summary"""
        predictions = self.get_predictions()
        
        return {
            'total_components': len(predictions),
            'healthy_count': sum(1 for p in predictions if p.health_score > 70),
            'warning_count': sum(1 for p in predictions if 40 < p.health_score <= 70),
            'critical_count': sum(1 for p in predictions if p.health_score <= 40),
            'next_maintenance': self.get_next_maintenance(),
            'predictions_by_component': {p.component: p.health_score for p in predictions}
        }


def create_predictive_system(num_motors: int = 4, battery_capacity: int = 5000) -> PredictiveMaintenanceSystem:
    """Factory function"""
    return PredictiveMaintenanceSystem(num_motors, battery_capacity)