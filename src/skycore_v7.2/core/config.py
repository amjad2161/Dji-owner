"""
SkyCore Professional Configuration (inspired by high-quality projects)
YAML + Environment + Validation
"""

import os
import yaml
from pydantic import BaseSettings, Field
from typing import Optional

class SkyCoreConfig(BaseSettings):
    """Professional configuration with validation"""
    environment: str = Field(default="production", env="SKYCORE_ENV")
    log_level: str = Field(default="INFO", env="SKYCORE_LOG_LEVEL")
    security_mode: bool = Field(default=True, env="SKYCORE_SECURITY_MODE")
    max_drones: int = Field(default=50, env="SKYCORE_MAX_DRONES")
    threat_threshold: float = Field(default=0.75, env="SKYCORE_THREAT_THRESHOLD")
    encrypted_commands: bool = Field(default=True, env="SKYCORE_ENCRYPTED")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

config = SkyCoreConfig()
print(f"✅ SkyCore Config loaded: {config.environment} mode")
