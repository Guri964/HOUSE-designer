from typing import List, Dict, Any

PLUMBING_TEMPLATES = {
    "bathroom": [
        {"type": "toilet", "label": "Toilet"},
        {"type": "washbasin", "label": "Washbasin"},
        {"type": "shower", "label": "Shower"}
    ],
    "kitchen": [
        {"type": "kitchen_sink", "label": "Kitchen Sink"},
        {"type": "water_inlet", "label": "Water Inlet"}
    ],
    "balcony": [
        {"type": "drain", "label": "Balcony Drain"}
    ]
}

def place_plumbing_in_room(room: Dict[str, Any]) -> List[Dict[str, Any]]:
    rtype = room["type"]
    templates = PLUMBING_TEMPLATES.get(rtype, [])
    if not templates:
        return []
    x, y, w, h = room["x"], room["y"], room["width"], room["height"]
    fixtures: List[Dict[str, Any]] = []
    for idx, tpl in enumerate(templates):
        if rtype == "bathroom":
            if tpl["type"] == "toilet":
                px, py = x + w - 2.2, y + h - 2.4
            elif tpl["type"] == "washbasin":
                px, py = x + 1.6, y + 1.6
            elif tpl["type"] == "shower":
                px, py = x + 1.6, y + h - 2.8
            else:
                px, py = x + w / 2, y + h / 2
        elif rtype == "kitchen":
            if tpl["type"] == "kitchen_sink":
                px, py = x + w * 0.70, y + 1.2
            else:
                px, py = x + w * 0.30, y + 1.2
        else:
            px, py = x + w / 2, y + h / 2

        fixtures.append({
            "id": f"{room['id']}_pl_{idx+1}",
            "type": tpl["type"],
            "label": tpl["label"],
            "x": round(px, 2),
            "y": round(py, 2),
            "room_id": room["id"]
        })
    return fixtures

def generate_plumbing(rooms: List[Dict[str, Any]]) -> tuple:
    fixtures: List[Dict[str, Any]] = []
    for r in rooms:
        items = place_plumbing_in_room(r)
        r["plumbing"] = items
        fixtures.extend(items)

    # generate routes: connect kitchen to nearest bathroom, bathrooms together
    # water supply line: polyline through plumbing fixtures sharing a wall corridor
    routes: List[Dict[str, Any]] = []
    # sort fixtures by type priority
    baths = [f for f in fixtures if f["type"] in ("toilet", "washbasin", "shower")]
    kitchens = [f for f in fixtures if f["type"] in ("kitchen_sink", "water_inlet")]
    # group per bathroom room proximity – connect fixtures inside same room first
    for room in [r for r in rooms if r["type"] == "bathroom"]:
        r_fix = [f for f in fixtures if f["room_id"] == room["id"]]
        for i in range(len(r_fix) - 1):
            a, b = r_fix[i], r_fix[i + 1]
            routes.append({
                "id": f"route_{a['id']}_to_{b['id']}",
                "from_fixture": a["id"],
                "to_fixture": b["id"],
                "path": [[a["x"], a["y"]], [b["x"], b["y"]]],
                "kind": "drainage" if "toilet" in b["type"] or "toilet" in a["type"] else "water_supply"
            })
    # inter-room: connect kitchen sink to nearest bathroom
    if kitchens and baths:
        # find closest pair between any kitchen fixture and any bath fixture
        # simplified: take first of each
        a = kitchens[0]
        # nearest bath
        best = min(baths, key=lambda b: ((a["x"] - b["x"])**2 + (a["y"] - b["y"])**2) ** 0.5)
        # path with orthogonal bend (manhattan)
        mid_x = (a["x"] + best["x"]) / 2
        routes.append({
            "id": f"route_{a['id']}_to_{best['id']}_main",
            "from_fixture": a["id"],
            "to_fixture": best["id"],
            "path": [[a["x"], a["y"]], [mid_x, a["y"]], [mid_x, best["y"]], [best["x"], best["y"]]],
            "kind": "water_supply"
        })
    # bathroom to bathroom interconnection
    bath_rooms = [r for r in rooms if r["type"] == "bathroom"]
    for i in range(len(bath_rooms) - 1):
        f1 = next((f for f in fixtures if f["room_id"] == bath_rooms[i]["id"]), None)
        f2 = next((f for f in fixtures if f["room_id"] == bath_rooms[i+1]["id"]), None)
        if f1 and f2:
            mid_x = (f1["x"] + f2["x"]) / 2
            routes.append({
                "id": f"route_{f1['id']}_to_{f2['id']}_interbath",
                "from_fixture": f1["id"],
                "to_fixture": f2["id"],
                "path": [[f1["x"], f1["y"]], [mid_x, f1["y"]], [mid_x, f2["y"]], [f2["x"], f2["y"]]],
                "kind": "drainage"
            })

    return fixtures, routes
