import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"
CONFIGS_DIR = ARTIFACTS_DIR / "configs"

# Candidate model paths - Claude notebook saves as gcn_model.pth, legacy as gcn_best.pt
GCN_MODEL_CANDIDATES = [
    str(MODELS_DIR / "gcn_model.pth"),
    str(MODELS_DIR / "gcn_best.pt"),
    str(ARTIFACTS_DIR / "gcn_model.pth"),
    str(ARTIFACTS_DIR / "gcn_best.pt"),
]
GCN_CONFIG_CANDIDATES = [
    str(CONFIGS_DIR / "gcn_config.json"),
    str(MODELS_DIR / "gcn_config.json"),
    str(ARTIFACTS_DIR / "gcn_config.json"),
]

GCN_MODEL_PATH = os.getenv("GCN_MODEL_PATH", str(MODELS_DIR / "gcn_model.pth"))
GCN_CONFIG_PATH = os.getenv("GCN_CONFIG_PATH", str(CONFIGS_DIR / "gcn_config.json"))
# Fallback legacy paths if new not found (handled in inference.py)
GCN_MODEL_PATH_LEGACY = str(MODELS_DIR / "gcn_best.pt")
GCN_CONFIG_PATH_LEGACY = str(CONFIGS_DIR / "gcn_config.json")
GCN_THRESHOLD = float(os.getenv("GCN_THRESHOLD", "0.5"))

# Claude notebook room type map (14 types) - used by new trained model
CLAUDE_ROOM_TYPE_MAP = {
    0: "LivingRoom",
    1: "MasterRoom",
    2: "Kitchen",
    3: "Bathroom",
    4: "DiningRoom",
    5: "ChildRoom",
    6: "StudyRoom",
    7: "SecondRoom",
    8: "GuestRoom",
    9: "Balcony",
    10: "Entrance",
    11: "Storage",
    12: "Wall",
    13: "Exterior"
}
# Map our 8 backend categories to Claude's 14 ids
BACKEND_TO_CLAUDE_ROOM_ID = {
    "living_room": 0,
    "bedroom": 1,  # MasterRoom
    "kitchen": 2,
    "bathroom": 3,
    "balcony": 9,
    "dining_room": 4,
    "corridor": 12,  # Wall as corridor proxy
    "entrance": 10
}
CLAUDE_IN_CHANNELS = 7
CLAUDE_HIDDEN_CHANNELS = 128
CLAUDE_FEATURE_ORDER = ["room_type", "width_norm", "height_norm", "area_norm", "aspect_ratio", "cx", "cy"]

COMPLIANCE_THRESHOLDS = {
    "fully_compliant": 0.85,
    "partially_compliant": 0.60
}

ROOM_CATEGORIES = [
    "living_room",
    "bedroom",
    "kitchen",
    "bathroom",
    "balcony",
    "dining_room",
    "corridor",
    "entrance"
]

ROOM_CATEGORY_TO_ID = {cat: idx for idx, cat in enumerate(ROOM_CATEGORIES)}
ID_TO_ROOM_CATEGORY = {v: k for k, v in ROOM_CATEGORY_TO_ID.items()}

DEFAULT_ROOM_AREAS = {
    "living_room": 280,
    "bedroom": 140,
    "kitchen": 100,
    "bathroom": 45,
    "balcony": 35,
    "dining_room": 110,
    "corridor": 30,
    "entrance": 15
}

MIN_ROOM_DIMS = {
    "living_room": (12, 10),
    "bedroom": (10, 10),
    "kitchen": (8, 7),
    "bathroom": (5, 6),
    "balcony": (6, 4),
    "dining_room": (8, 8),
    "corridor": (3, 6),
    "entrance": (3, 3),
    "staircase": (4, 8)
}

STYLE_PRESETS = ["modern", "traditional", "minimal", "luxury", "contemporary", "classic"]

DIRECTIONS = ["north", "south", "east", "west", "north_east", "north_west", "south_east", "south_west"]

DEFAULT_RATE_PROFILE = "india_tier2_2025"

COST_RATE_PROFILES = {
    "india_tier2_2025": {
        "label": "India Tier-2 City 2025 Estimate",
        "currency": "INR",
        "rates": {
            "civil_per_sqft": 1650,
            "flooring_per_sqft": 120,
            "painting_per_sqft": 45,
            "doors_windows_per_sqft": 180,
            "electrical_per_sqft": 110,
            "plumbing_per_sqft": 95,
            "lighting_per_fixture": 2200,
            "sanitary_per_bathroom": 28500,
            "kitchen_per_unit": 85000,
            "furniture_per_bedroom": 45000,
            "furniture_living": 65000,
            "balcony_per_unit": 12000,
            "contingency_pct": 0.05
        }
    },
    "india_metro_2025": {
        "label": "India Metro City 2025 Estimate",
        "currency": "INR",
        "rates": {
            "civil_per_sqft": 2100,
            "flooring_per_sqft": 160,
            "painting_per_sqft": 55,
            "doors_windows_per_sqft": 220,
            "electrical_per_sqft": 140,
            "plumbing_per_sqft": 120,
            "lighting_per_fixture": 2800,
            "sanitary_per_bathroom": 35000,
            "kitchen_per_unit": 110000,
            "furniture_per_bedroom": 58000,
            "furniture_living": 82000,
            "balcony_per_unit": 15000,
            "contingency_pct": 0.06
        }
    }
}
