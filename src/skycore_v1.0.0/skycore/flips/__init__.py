"""
Flight Tricks and Stunts Package
Pre-programmed aerial maneuvers, dynamic shows, performance routines
"""

from .flips import FlipManager, FlipType, FlipSequence, ShowPattern
from .acrobatic import AcrobaticController, ManeuverLibrary

__all__ = ['FlipManager', 'FlipType', 'FlipSequence', 'ShowPattern', 'AcrobaticController', 'ManeuverLibrary']