from typing import Dict, Any

COMPASS_ANGLES = {
    "north": 0,
    "north_east": 45,
    "east": 90,
    "south_east": 135,
    "south": 180,
    "south_west": 225,
    "west": 270,
    "north_west": 315
}

def orientation_metadata(requested: str, width: float, height: float) -> Dict[str, Any]:
    angle = COMPASS_ANGLES.get(requested, 90)
    # entrance wall based on direction
    wall_map = {
        "north": "top",
        "east": "right",
        "south": "bottom",
        "west": "left",
        "north_east": "top_right",
        "north_west": "top_left",
        "south_east": "bottom_right",
        "south_west": "bottom_left"
    }
    wall = wall_map.get(requested, "right")
    return {
        "requested_direction": requested,
        "entrance_wall": wall,
        "north_angle_deg": angle,
        "compass_label": requested.replace("_", "-").upper(),
        "width": width,
        "height": height,
        "note": f"Top of 2D plan is NORTH (0°). Entrance on {wall} wall per {requested} facing."
    }
