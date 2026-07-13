"""
SkyCore Live Collaborative SLAM v2.0 (Real-time)
Multiple drones build and share a live 3D map in real-time
"""

from typing import Dict, List, Tuple
import time

class LiveCollaborativeSLAM:
    def __init__(self):
        self.global_map: List[Tuple] = []
        self.drone_poses: Dict[str, dict] = {}
        self.last_update = time.time()

    def update_drone(self, drone_id: str, position: Tuple, velocity: Tuple, map_points: List[Tuple]):
        """Real-time update from a drone"""
        self.drone_poses[drone_id] = {
            "position": position,
            "velocity": velocity,
            "last_update": time.time()
        }
        self.global_map.extend(map_points)
        
        # Clean old points (keep only recent)
        if len(self.global_map) > 5000:
            self.global_map = self.global_map[-4000:]
        
        print(f"🗺️ [Live SLAM] {drone_id} updated | Map points: {len(self.global_map)}")

    def get_shared_map(self) -> List[Tuple]:
        """Get the current shared 3D map"""
        return self.global_map

    def detect_loop_closure(self, drone_id: str, position: Tuple) -> bool:
        """Detect if any drone returned to a known area"""
        for known_id, info in self.drone_poses.items():
            if known_id != drone_id:
                dist = ((position[0] - info["position"][0])**2 + 
                       (position[1] - info["position"][1])**2)**0.5
                if dist < 8:  # 8 meter threshold
                    print(f"🔄 [Live SLAM] Loop closure: {drone_id} + {known_id}")
                    return True
        return False

    def get_drone_positions(self) -> Dict:
        return {k: v["position"] for k, v in self.drone_poses.items()}
