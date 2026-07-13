"""
Compass and Magnetometer Package
3-axis magnetometer, compass heading, magnetic deviation
"""

from .magnetometer import Magnetometer, HeadingData, MagneticCalibration

__all__ = ['Magnetometer', 'HeadingData', 'MagneticCalibration']