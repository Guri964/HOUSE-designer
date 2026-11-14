from typing import List, Dict, Any
import uuid

FURNITURE_TEMPLATES = {
    "bedroom": [
        {"type": "bed", "w": 6.5, "h": 8.0, "label": "Double Bed"},
        {"type": "wardrobe", "w": 6.0, "h": 2.5, "label": "Wardrobe"},
        {"type": "study_table", "w": 3.5, "h": 2.0, "label": "Study Table"},
        {"type": "side_table", "w": 1.5, "h": 1.5, "label": "Side Table"}
    ],
    "living_room": [
        {"type": "sofa", "w": 7.0, "h": 3.0, "label": "Sofa 3-Seater"},
        {"type": "sofa_single", "w": 3.5, "h": 3.0, "label": "Armchair"},
        {"type": "coffee_table", "w": 4.0, "h": 2.5, "label": "Coffee Table"},
        {"type": "tv_unit", "w": 5.5, "h": 1.8, "label": "TV Unit"}
    ],
    "kitchen": [
        {"type": "counter", "w": 8.0, "h": 2.2, "label": "Kitchen Counter"},
        {"type": "refrigerator", "w": 2.8, "h": 2.8, "label": "Refrigerator"},
        {"type": "dining_table", "w": 3.5, "h": 3.5, "label": "Dining Nook"},
        {"type": "cabinet", "w": 5.0, "h": 1.5, "label": "Wall Cabinet"}
    ],
    "dining_room": [
        {"type": "dining_table", "w": 5.5, "h": 4.0, "label": "Dining Table 4S"},
        {"type": "chair", "w": 1.6, "h": 1.6, "label": "Chair"},
    ],
    "bathroom": [
        {"type": "toilet", "w": 1.8, "h": 2.2, "label": "Toilet"},
        {"type": "washbasin", "w": 2.0, "h": 1.4, "label": "Washbasin"},
        {"type": "shower", "w": 2.5, "h": 2.5, "label": "Shower"}
    ],
    "balcony": [
        {"type": "chair", "w": 1.8, "h": 1.8, "label": "Outdoor Chair"},
        {"type": "table_small", "w": 1.5, "h": 1.5, "label": "Side Table"}
    ]
}

CLEARANCE = 1.2

def place_furniture_in_room(room: Dict[str, Any]) -> List[Dict[str, Any]]:
    rtype = room["type"]
    templates = FURNITURE_TEMPLATES.get(rtype, [])
    if not templates:
        return []
    placed: List[Dict[str, Any]] = []
    x, y, w, h = room["x"], room["y"], room["width"], room["height"]
    # simple wall-aligned placement with clearance checks
    # position map: try each wall side
    candidates = []
    for t in templates:
        tw, th = t["w"], t["h"]
        if tw + 2 > w or th + 2 > h:
            # scale down if too large
            scale = min((w - 2) / tw, (h - 2) / th, 1.0)
            tw *= scale
            th *= scale
        candidates.append((t, tw, th))

    # placement heuristics per type
    # bed: against longest wall, centered
    # sofas: along wall opposite window
    # counters: along north/east wall
    # wardrobes: corner

    # we place sequentially, avoiding overlap
    def overlaps(px, py, pw, ph):
        for p in placed:
            if not (px + pw + CLEARANCE <= p["x"] or p["x"] + p["width"] + CLEARANCE <= px or py + ph + CLEARANCE <= p["y"] or p["y"] + p["height"] + CLEARANCE <= py):
                return True
        return False

    for (tpl, tw, th) in candidates:
        placed_success = False
        # try four positions: top wall, bottom, left, right
        tries = []
        # top wall (y near room y)
        tries.append((x + (w - tw) / 2, y + 0.6, tw, th))
        tries.append((x + w - tw - 0.6, y + (h - th) / 2, th, tw))  # rotate attempt -> swap
        tries.append((x + 0.6, y + (h - th) / 2, tw, th))
        tries.append((x + (w - tw) / 2, y + h - th - 0.6, tw, th))
        # also corners
        tries.append((x + 0.6, y + 0.6, tw, th))
        tries.append((x + w - tw - 0.6, y + 0.6, tw, th))
        tries.append((x + 0.6, y + h - th - 0.6, tw, th))
        tries.append((x + w - tw - 0.6, y + h - th - 0.6, tw, th))

        for (px, py, pw, ph) in tries:
            # check inside
            if px < x + 0.3 or py < y + 0.3 or px + pw > x + w - 0.3 or py + ph > y + h - 0.3:
                continue
            # clearance from doors/windows
            # simplified: keep 2ft away from doors
            blocked = False
            for d in room.get("doors", []):
                # door position approximate: if door x near furniture, block
                dx, dy = d.get("x", x), d.get("y", y)
                if abs(px - dx) < 3.5 and abs(py - dy) < 3.5:
                    blocked = True
            if blocked:
                continue
            if not overlaps(px, py, pw, ph):
                placed.append({
                    "id": f"{room['id']}_fur_{len(placed)+1}",
                    "type": tpl["type"],
                    "label": tpl["label"],
                    "x": round(px, 2),
                    "y": round(py, 2),
                    "width": round(pw, 2),
                    "height": round(ph, 2),
                    "rotation": 0
                })
                placed_success = True
                break
        # if not placed, skip that item
        # limit furniture per room to keep space
        if len(placed) >= 4 and rtype in ("bedroom", "living_room"):
            break
        if len(placed) >= 3 and rtype in ("kitchen", "bathroom"):
            break

    return placed

def generate_furniture(rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    all_fur = []
    for r in rooms:
        items = place_furniture_in_room(r)
        r["furniture"] = items
        all_fur.extend([{**it, "room_id": r["id"], "room_type": r["type"]} for it in items])
    return all_fur
