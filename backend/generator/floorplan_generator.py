from typing import Dict, List, Any, Tuple
import math

from ..config import DEFAULT_ROOM_AREAS, MIN_ROOM_DIMS
from .geometry import rects_overlap, adjacency_from_geometry
from .furniture import generate_furniture
from .lighting import generate_lighting
from .plumbing import generate_plumbing
from .orientation import orientation_metadata

ROOM_TYPE_PRIORITY = ["living_room", "kitchen", "bedroom", "bathroom", "dining_room", "balcony", "corridor"]

def _distribute_areas(parsed: Dict[str, Any]) -> Dict[str, List[float]]:
    total = float(parsed["total_area_sqft"])
    bedrooms = int(parsed["bedrooms"])
    bathrooms = int(parsed["bathrooms"])
    balconies = int(parsed.get("balconies", 0))
    dining = int(parsed.get("dining_rooms", 0))
    base = {}
    base["living_room"] = [total * 0.22]
    if dining > 0:
        base["living_room"] = [total * 0.18]
        base["dining_room"] = [total * 0.10]
    base["kitchen"] = [total * 0.11]
    base["bedroom"] = [total * 0.16] * bedrooms
    base["bathroom"] = [total * 0.05] * bathrooms
    if balconies > 0:
        base["balcony"] = [total * 0.03] * balconies
    current_sum = sum(sum(v) for v in base.values())
    circulation = total * 0.06
    scale = (total - circulation) / current_sum if current_sum > 0 else 1
    for k in list(base.keys()):
        base[k] = [a * scale for a in base[k]]
    for rtype, areas in base.items():
        for i, a in enumerate(areas):
            min_a = DEFAULT_ROOM_AREAS.get(rtype, 60)
            if a < min_a:
                base[rtype][i] = min_a
    total_rooms = sum(sum(v) for v in base.values())
    if total_rooms + circulation > total:
        excess = total_rooms + circulation - total
        reduce_factor = (total_rooms - excess) / total_rooms if total_rooms else 1
        for k in base:
            base[k] = [a * reduce_factor for a in base[k]]
    return base

def _place_rooms_tiled(area_map: Dict[str, List[float]], total_area: float, entrance_dir: str, style: str) -> Tuple[List[Dict[str, Any]], float, float]:
    # Row-band tiling: ensures no gaps and full adjacency
    # Find optimal width to minimize area overshoot due to min-height clamping
    # Prepare ordered list for width search
    ordered_for_search: List[Tuple[str, float]] = []
    group_order_tmp = ["living_room", "dining_room", "kitchen", "bedroom", "bathroom", "balcony", "corridor"]
    for rtype in group_order_tmp:
        if rtype in area_map:
            for a in area_map[rtype]:
                ordered_for_search.append((rtype, a))
    # Build groups for search (same logic as below)
    def groups_for_width(Wtest: float):
        # rebuild groups quickly for evaluation
        g1 = [(t, a) for t, a in ordered_for_search if t in ("living_room", "dining_room", "kitchen")]
        g2 = [(t, a) for t, a in ordered_for_search if t == "bedroom"]
        g3 = [(t, a) for t, a in ordered_for_search if t in ("bathroom", "balcony", "corridor")]
        gs = [g for g in [g1, g2, g3] if g]
        if not gs:
            gs = [ordered_for_search]
        g_areas = [sum(a for _, a in g) for g in gs]
        g_mins = []
        for g in gs:
            mh = 0.0
            for rtype, _ in g:
                min_w, min_h = MIN_ROOM_DIMS.get(rtype, (8, 8))
                mh = max(mh, float(min(min_w, min_h)))
            g_mins.append(mh)
        heights = [max(a / Wtest, mh) for a, mh in zip(g_areas, g_mins)]
        total_h = sum(heights)
        total_area_actual = Wtest * total_h
        # penalty for extreme aspect
        aspect_penalty = 0
        if total_h > Wtest * 1.9 or Wtest > total_h * 2.2:
            aspect_penalty = abs(total_h - Wtest) * 0.1
        return abs(total_area_actual - total_area) + aspect_penalty, total_h, g_areas, g_mins, heights, gs

    # search best W
    best_W = None
    best_cost = float("inf")
    best_meta = None
    # style affects initial guess but search covers range
    for Wcand in [x * 0.5 for x in range(40, 130)]:  # 20 to 64.5 step 0.5
        if Wcand < 18 or Wcand > 64:
            continue
        cost, th, ga, gm, hs, gs = groups_for_width(Wcand)
        # also enforce per-room min width after scaling: if any room width < min_w, penalize
        # we can check quickly: for each group, width = area / h_scaled? approximate
        # skip detailed
        if cost < best_cost:
            best_cost = cost
            best_W = Wcand
            best_meta = (th, ga, gm, hs, gs)
    # fallback if not found
    if best_W is None:
        aspect = 1.38
        if style in ("luxury", "contemporary"):
            aspect = 1.45
        best_W = max(20.0, min(62.0, math.sqrt(total_area * aspect)))
    W = float(best_W)
    # Prepare ordered room list
    ordered: List[Tuple[str, float]] = []
    # order groups: living/kitchen/dining top band, bedrooms middle, baths+balk bottom
    group_order = ["living_room", "dining_room", "kitchen", "bedroom", "bathroom", "balcony", "corridor"]
    for rtype in group_order:
        if rtype in area_map:
            for a in area_map[rtype]:
                ordered.append((rtype, a))

    # Build groups for banding
    groups: List[List[Tuple[str, float]]] = []
    # Group definitions
    # G1: living + dining + kitchen
    g1 = [(t, a) for t, a in ordered if t in ("living_room", "dining_room", "kitchen")]
    g2 = [(t, a) for t, a in ordered if t == "bedroom"]
    g3 = [(t, a) for t, a in ordered if t in ("bathroom", "balcony", "corridor")]
    for g in [g1, g2, g3]:
        if g:
            groups.append(g)

    # If groups empty edge case
    if not groups:
        groups = [ordered]

    # Compute group areas
    group_areas = [sum(a for _, a in g) for g in groups]
    # Compute minimum heights required per group (max of smaller side among its rooms)
    min_heights = []
    for g in groups:
        mh = 0.0
        for rtype, _ in g:
            min_w, min_h = MIN_ROOM_DIMS.get(rtype, (8, 8))
            # we can rotate, so min is smaller side
            mh = max(mh, float(min(min_w, min_h)))
        min_heights.append(mh)

    # Initial height per group = area / W
    heights = [area / W for area in group_areas]
    # Enforce min heights
    for i in range(len(heights)):
        if heights[i] < min_heights[i]:
            heights[i] = float(min_heights[i])

    # Recompute total H as sum heights
    H = sum(heights)

    # Now if total area / W != H due to clamping, we will have slightly larger total footprint than requested, which is acceptable and captures realism
    # But if H becomes very tall (> W*1.8) we slightly increase W to keep aspect near
    if H > W * 1.85:
        newW = math.sqrt(sum(group_areas) * 0.95 / (H / W))  # try widen
        # but keep simple: increase W by 12%
        W = W * 1.18
        # recompute heights with new W
        heights = [area / W for area in group_areas]
        for i in range(len(heights)):
            if heights[i] < min_heights[i]:
                heights[i] = float(min_heights[i])
        H = sum(heights)

    rooms: List[Dict[str, Any]] = []
    uid = 1
    y_cursor = 0.0
    # For balcony, we sometimes want it attached as extension outside main width; handle specially if only one balcony to give outdoor feel
    # But keep within tiled logic for adjacency: balcony width larger aspect

    for gi, grp in enumerate(groups):
        h = heights[gi]
        # Within group, split width proportionally to area
        total_g_area = group_areas[gi]
        x_cursor = 0.0
        for (rtype, area) in grp:
            # width = area / h
            w = area / h if h > 0.1 else area / 10.0
            # Clamp min width
            min_w, min_h = MIN_ROOM_DIMS.get(rtype, (8, 8))
            # allow rotation: ensure w >= min_w and h >= min_h or swapped?
            # For corridor/balcony we allow thin
            if rtype == "balcony":
                # balcony should be shallower height but wide: ensure at least 6 width
                if w < 10:
                    # adjust: give balcony more width by borrowing from group? but keep simple: scale
                    w = max(w, 9.0)
                    # adjust height accordingly keep area
                    # but height fixed per group; we will keep w as is and adjust area tolerance instead
                    pass
            else:
                if w < min_w - 0.5:
                    # increase w to min and reduce subsequent room widths proportionally? simplified: set w to min_w and keep h, area will be larger but okay
                    w = float(min_w)
            # Ensure room does not exceed remaining width due to rounding
            remaining = W - x_cursor
            if w > remaining + 0.05:
                w = remaining
            if w < 3:
                w = remaining
            # height is h for all rooms in group (strip height)
            # For bedrooms we might want slightly different height within group to vary aspect? But keep uniform for tiling guarantee
            rw = round(w, 2)
            rh = round(h, 2)
            # For bathroom inside g3, height may be small (4-5) which violates min_h 5-6, but we clamped group height to at least 6 maybe? Already enforced via min_heights
            # Create room
            count_same = len([r for r in rooms if r["type"] == rtype]) + 1
            total_same = len([t for t, _ in ordered if t == rtype])
            label = rtype.replace("_", " ").title()
            if total_same > 1:
                label = f"{label} {count_same}"
            room = {
                "id": f"room_{uid}",
                "type": rtype,
                "label": label,
                "x": round(x_cursor, 2),
                "y": round(y_cursor, 2),
                "width": rw,
                "height": rh,
                "area": round(rw * rh, 2),
                "target_area": round(area, 2),
                "doors": [],
                "windows": [],
                "furniture": [],
                "lighting": [],
                "plumbing": []
            }
            rooms.append(room)
            uid += 1
            x_cursor += w
        # gap correction: distribute gap proportionally across row to preserve area ratios
        row_rooms = [r for r in rooms if abs(r["y"] - y_cursor) < 0.01]
        if row_rooms:
            total_row_w = sum(r["width"] for r in row_rooms)
            gap = W - total_row_w
            if abs(gap) > 0.08:
                scale = W / total_row_w if total_row_w > 0 else 1
                cur_x = 0.0
                for rr in row_rooms:
                    new_w = round(rr["width"] * scale, 2)
                    # adjust x to follow scaled packing
                    rr["x"] = round(cur_x, 2)
                    rr["width"] = new_w
                    rr["area"] = round(rr["width"] * rr["height"], 2)
                    cur_x += new_w
                # due to rounding, force last width to fill exactly
                if row_rooms:
                    row_rooms[-1]["width"] = round(W - sum(r["width"] for r in row_rooms[:-1]), 2)
                    row_rooms[-1]["area"] = round(row_rooms[-1]["width"] * row_rooms[-1]["height"], 2)
        y_cursor += h

    # After tiling, ensure no zero-area
    # Recompute footprint
    W = max(r["x"] + r["width"] for r in rooms) if rooms else W
    H = max(r["y"] + r["height"] for r in rooms) if rooms else H

    # Add doors and windows
    for r in rooms:
        # door centered on south wall (shared edge with next row or interior)
        r["doors"] = [{"id": f"{r['id']}_door_1", "wall": "south", "x": round(r["x"] + r["width"] / 2, 2), "y": round(r["y"] + r["height"], 2), "width": 3.0}]
        if r["type"] in ("bedroom", "living_room", "kitchen"):
            r["windows"] = [{"id": f"{r['id']}_win_1", "wall": "north", "x": round(r["x"] + r["width"] / 2, 2), "y": round(r["y"], 2), "width": 4.0}]
        elif r["type"] == "bathroom":
            r["windows"] = [{"id": f"{r['id']}_win_1", "wall": "north", "x": round(r["x"] + r["width"] / 2, 2), "y": round(r["y"], 2), "width": 2.0}]
        elif r["type"] == "balcony":
            # balcony open: no window, door to bedroom
            r["windows"] = []
            # balcony door wall is west/east shared with bedroom/bath
        else:
            r["windows"] = []

    # Small jitter to avoid perfect alignment looking fake: nudge by 0? Keep clean for adjacency tolerance.

    return rooms, round(W, 2), round(H, 2)

def generate_floorplan(parsed: Dict[str, Any]) -> Dict[str, Any]:
    total_area = float(parsed["total_area_sqft"])
    entrance_dir = parsed.get("main_entrance_direction", "east")
    style = parsed.get("style", "modern")
    area_map = _distribute_areas(parsed)
    rooms, footprint_w, footprint_h = _place_rooms_tiled(area_map, total_area, entrance_dir, style)
    actual_total = sum(r["area"] for r in rooms)
    orient = orientation_metadata(entrance_dir, footprint_w, footprint_h)
    adj = adjacency_from_geometry(rooms)
    furniture = generate_furniture(rooms)
    lighting = generate_lighting(rooms)
    plumbing_fixtures, plumbing_routes = generate_plumbing(rooms)
    doors = []
    windows = []
    for r in rooms:
        doors.extend(r["doors"])
        windows.extend(r["windows"])
    layout = {
        "width": footprint_w,
        "height": footprint_h,
        "total_area": round(actual_total, 2),
        "built_up_area": round(total_area, 2),
        "rooms": rooms,
        "furniture": furniture,
        "lighting": lighting,
        "plumbing_fixtures": plumbing_fixtures,
        "plumbing_routes": plumbing_routes,
        "doors": doors,
        "windows": windows,
        "orientation": orient,
        "adjacency": adj,
        "metadata": {
            "style": style,
            "entrance_direction": entrance_dir,
            "parsed_input": parsed,
            "generation_notes": [
                f"Row-band tiled {len(rooms)} rooms across {footprint_w:.1f} x {footprint_h:.1f} ft footprint",
                f"Actual room area sum {actual_total:.1f} vs requested {total_area:.1f}",
                f"Adjacency pairs: {len(adj)}",
            ],
            "warnings": parsed.get("warnings", [])
        }
    }
    return layout
