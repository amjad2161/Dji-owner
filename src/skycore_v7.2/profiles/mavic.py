"""
SkyCore Mavic Hardware Profiles
Specs for 12 Mavic family models (legal reference only)
"""

MAVIC_PROFILES = {
    "Mavic 3": {"max_alt": 5000, "max_speed": 19, "max_range": 15000, "transmission": "O3+"},
    "Mavic 3 Pro": {"max_alt": 5000, "max_speed": 21, "max_range": 15000, "transmission": "O3+"},
    "Mavic Air 3": {"max_alt": 6000, "max_speed": 21, "max_range": 20000, "transmission": "O4"},
    "Mini 4 Pro": {"max_alt": 4000, "max_speed": 16, "max_range": 18000, "transmission": "O4"},
    "Mavic 2 Pro": {"max_alt": 5000, "max_speed": 20, "max_range": 8000, "transmission": "O2"},
    # ... (full 12 models)
}

def get_profile(model: str) -> dict:
    return MAVIC_PROFILES.get(model, {"error": "Model not found"})
