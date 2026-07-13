"""
SkyCore Redundancy & Fail-safe (military-grade)
Multiple backup systems + automatic failover
"""

from typing import Callable, Any

class RedundancyManager:
    def __init__(self):
        self.primary = None
        self.backup = None
        self.failover_count = 0

    def set_primary(self, system: Callable):
        self.primary = system

    def set_backup(self, system: Callable):
        self.backup = system

    async def execute_with_failover(self, *args, **kwargs) -> Any:
        try:
            return await self.primary(*args, **kwargs)
        except Exception as e:
            print(f"⚠️ Primary failed: {e} → Switching to backup")
            self.failover_count += 1
            if self.backup:
                return await self.backup(*args, **kwargs)
            raise
