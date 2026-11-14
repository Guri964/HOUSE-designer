from ..config import COST_RATE_PROFILES

def get_rate_profile(profile_id: str) -> dict:
    return COST_RATE_PROFILES.get(profile_id, COST_RATE_PROFILES["india_tier2_2025"])

def list_profiles() -> list:
    return [{"id": k, "label": v["label"], "currency": v["currency"]} for k, v in COST_RATE_PROFILES.items()]
