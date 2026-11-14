from typing import List, Dict, Any

LIGHTING_TEMPLATES = {
    "living_room": [
        {"type": "ceiling_light", "label": "Central Ceiling", "count": 1},
        {"type": "recessed_light", "label": "Recessed", "count": 2},
        {"type": "pendant_light", "label": "Pendant", "count": 1},
    ],
    "bedroom": [
        {"type": "ceiling_light", "label": "Ceiling", "count": 1},
        {"type": "pendant_light", "label": "Bedside Pendant", "count": 2},
    ],
    "kitchen": [
        {"type": "recessed_light", "label": "Kitchen Task Light", "count": 2},
        {"type": "ceiling_light", "label": "Kitchen Ceiling", "count": 1},
    ],
    "bathroom": [
        {"type": "ceiling_light", "label": "Bath Ceiling", "count": 1},
    ],
    "balcony": [
        {"type": "wall_light", "label": "Balcony Wall", "count": 1},
    ],
    "dining_room": [
        {"type": "pendant_light", "label": "Dining Pendant", "count": 1},
        {"type": "recessed_light", "label": "Recessed", "count": 2},
    ],
    "corridor": [
        {"type": "recessed_light", "label": "Corridor", "count": 1},
    ],
    "entrance": [
        {"type": "wall_light", "label": "Entrance", "count": 1},
    ]
}

def place_lighting_in_room(room: Dict[str, Any]) -> List[Dict[str, Any]]:
    rtype = room["type"]
    templates = LIGHTING_TEMPLATES.get(rtype, [{"type": "ceiling_light", "label": "Ceiling", "count": 1}])
    x, y, w, h = room["x"], room["y"], room["width"], room["height"]
    cx, cy = x + w / 2, y + h / 2
    fixtures: List[Dict[str, Any]] = []
    fid = 1
    for tpl in templates:
        for i in range(tpl["count"]):
            if tpl["type"] == "ceiling_light":
                lx, ly = cx, cy
            elif tpl["type"] == "recessed_light":
                # offset in grid
                if i == 0:
                    lx, ly = x + w * 0.30, y + h * 0.35
                else:
                    lx, ly = x + w * 0.70, y + h * 0.65
            elif tpl["type"] == "pendant_light":
                if rtype == "bedroom":
                    lx = x + w * (0.30 if i == 0 else 0.70)
                    ly = y + h * 0.55
                elif rtype == "dining_room":
                    lx, ly = cx, cy - 1.5
                else:
                    lx, ly = x + w * 0.75, y + h * 0.30
            elif tpl["type"] == "wall_light":
                lx, ly = x + w * 0.50, y + 0.7
            else:
                lx, ly = cx + (i * 1.2), cy

            fixtures.append({
                "id": f"{room['id']}_lt_{fid}",
                "type": tpl["type"],
                "label": tpl["label"],
                "x": round(lx, 2),
                "y": round(ly, 2),
                "room_id": room["id"]
            })
            fid += 1
            if len(fixtures) >= 4:
                break
    return fixtures

def generate_lighting(rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    all_lt: List[Dict[str, Any]] = []
    for r in rooms:
        items = place_lighting_in_room(r)
        r["lighting"] = items
        all_lt.extend(items)
    return all_lt
