from typing import Dict, List, Any, Tuple
import math

from ..config import DEFAULT_ROOM_AREAS, MIN_ROOM_DIMS
from .geometry import rects_overlap, adjacency_from_geometry
from .furniture import generate_furniture
from .lighting import generate_lighting
from .plumbing import generate_plumbing
from .orientation import orientation_metadata

ROOM_TYPE_PRIORITY = ["living_room", "kitchen", "bedroom", "bathroom", "dining_room", "balcony", "corridor"]

# Multi-floor constants
STAIR_WIDTH = 4.0          # ft - clear stair width
STAIR_DEPTH = 10.0         # ft - stair run along the plan depth axis
STORY_HEIGHT = 10.0        # ft - floor-to-floor height used for 3D stacking

ORDINAL_FLOOR_NAMES = ["Ground Floor", "First Floor", "Second Floor",
                       "Third Floor", "Fourth Floor", "Fifth Floor"]


def _floor_label(index: int) -> str:
    if 0 <= index < len(ORDINAL_FLOOR_NAMES):
        return ORDINAL_FLOOR_NAMES[index]
    return f"Floor {index + 1}"


def _distribute_areas(parsed: Dict[str, Any]) -> Dict[str, List[float]]:
    total = float(parsed["total_area_sqft"])
    bedrooms = int(parsed["bedrooms"])
    bathrooms = int(parsed["bathrooms"])
    balconies = int(parsed.get("balconies", 0))
    dining = int(parsed.get("dining_rooms", 0))
    base = {}
    if int(parsed.get("living_rooms", 1)) > 0:
        base["living_room"] = [total * 0.22]
        if dining > 0:
            base["living_room"] = [total * 0.18]
            base["dining_room"] = [total * 0.10]
    if int(parsed.get("kitchens", 1)) > 0:
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


def _place_floor_at_fixed_width(area_map: Dict[str, List[float]], W: float,
                               y0: float = 0.0,
                               min_dim_scale: float = 1.0) -> Tuple[List[Dict[str, Any]], float]:
    """Place rooms into row bands at a FIXED width W starting at depth y0.

    Used for multi-floor layouts where every floor shares one footprint so the
    staircase (reserved at the bottom-right corner) stays aligned across floors.
    Doors/windows are NOT added here; the layout assembler adds them afterwards.
    min_dim_scale relaxes minimum dimensions (e.g. 0.7 = 30% smaller) for small
    multi-floor budgets where standard min dims cannot fit.
    Returns (rooms, height_used).
    """
    ordered: List[Tuple[str, float]] = []
    group_order = ["living_room", "dining_room", "kitchen", "bedroom", "bathroom", "balcony", "corridor"]
    for rtype in group_order:
        if rtype in area_map:
            for a in area_map[rtype]:
                ordered.append((rtype, a))

    groups: List[List[Tuple[str, float]]] = []
    g1 = [(t, a) for t, a in ordered if t in ("living_room", "dining_room", "kitchen")]
    g2 = [(t, a) for t, a in ordered if t == "bedroom"]
    g3 = [(t, a) for t, a in ordered if t in ("bathroom", "balcony", "corridor")]
    for g in [g1, g2, g3]:
        if g:
            groups.append(g)
    if not groups:
        groups = [ordered]

    group_areas = [sum(a for _, a in g) for g in groups]
    min_heights = []
    for g in groups:
        mh = 0.0
        for rtype, _ in g:
            min_w, min_h = MIN_ROOM_DIMS.get(rtype, (8, 8))
            mh = max(mh, float(min(min_w, min_h)) * min_dim_scale)
        min_heights.append(mh)

    heights = [area / W for area in group_areas]
    for i in range(len(heights)):
        if heights[i] < min_heights[i]:
            heights[i] = float(min_heights[i])

    rooms: List[Dict[str, Any]] = []
    uid = 1
    y_cursor = y0
    for gi, grp in enumerate(groups):
        h = heights[gi]
        total_g_area = group_areas[gi]
        x_cursor = 0.0
        for (rtype, area) in grp:
            w = area / h if h > 0.1 else area / 10.0
            min_w, min_h = MIN_ROOM_DIMS.get(rtype, (8, 8))
            min_w = min_w * min_dim_scale
            min_h = min_h * min_dim_scale
            if rtype == "balcony":
                if w < 10:
                    w = max(w, 9.0)
            else:
                if w < min_w - 0.5:
                    w = float(min_w)
            remaining = W - x_cursor
            if w > remaining + 0.05:
                w = remaining
            if w < 3:
                w = remaining
            rw = round(w, 2)
            rh = round(h, 2)
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
        row_rooms = [r for r in rooms if abs(r["y"] - y_cursor) < 0.01]
        if row_rooms:
            total_row_w = sum(r["width"] for r in row_rooms)
            gap = W - total_row_w
            if abs(gap) > 0.08:
                scale = W / total_row_w if total_row_w > 0 else 1
                cur_x = 0.0
                for rr in row_rooms:
                    new_w = round(rr["width"] * scale, 2)
                    rr["x"] = round(cur_x, 2)
                    rr["width"] = new_w
                    rr["area"] = round(rr["width"] * rr["height"], 2)
                    cur_x += new_w
                if row_rooms:
                    row_rooms[-1]["width"] = round(W - sum(r["width"] for r in row_rooms[:-1]), 2)
                    row_rooms[-1]["area"] = round(row_rooms[-1]["width"] * row_rooms[-1]["height"], 2)
        y_cursor += h

    H_used = (y_cursor - y0) if rooms else 0.0
    W_out = max(r["x"] + r["width"] for r in rooms) if rooms else W
    return rooms, round(H_used, 2), round(W_out, 2)


def _place_floor_with_openings(area_map: Dict[str, List[float]], W: float,
                               entrance_dir: str, is_ground_floor: bool,
                               y0: float = 0.0,
                               min_dim_scale: float = 1.0
                               ) -> Tuple[List[Dict[str, Any]], float]:
    """Place rooms on a floor and add entrance door, internal doors, and windows."""
    rooms, h_used, w_out = _place_floor_at_fixed_width(
        area_map, W, y0=y0, min_dim_scale=min_dim_scale)
    _add_doors_windows_to_floor(rooms, W, h_used + y0, entrance_dir, is_ground_floor)
    return rooms, h_used


def _exterior_wall_for_direction(entrance_dir: str) -> str:
    """Map facing direction to the exterior wall where the entrance goes.
    east -> right (east), north -> top (north), etc."""
    return {
        "north": "north",
        "south": "south",
        "east": "east",
        "west": "west",
        "north_east": "east",
        "north_west": "west",
        "south_east": "east",
        "south_west": "west",
    }.get(entrance_dir, "east")


def _room_touches_wall(r: Dict[str, Any], W: float, H: float, wall: str) -> bool:
    """Check if a room touches a given exterior wall of the footprint."""
    eps = 0.5
    if wall == "north":
        return r["y"] < eps
    if wall == "south":
        return r["y"] + r["height"] > H - eps
    if wall == "east":
        return r["x"] + r["width"] > W - eps
    if wall == "west":
        return r["x"] < eps
    return False


def _add_entrance_door(rooms: List[Dict[str, Any]], W: float, H: float,
                       entrance_dir: str) -> Dict[str, Any] | None:
    """Place the main entrance door on the exterior wall per facing direction,
    in the living room (ground floor). Adds the door directly to the room's
    doors list. Returns the door dict or None."""
    wall = _exterior_wall_for_direction(entrance_dir)
    # Prefer living room, fall back to any non-staircase room touching the wall
    candidates = [r for r in rooms if r["type"] == "living_room" and
                  _room_touches_wall(r, W, H, wall)]
    if not candidates:
        candidates = [r for r in rooms if r["type"] != "staircase" and
                      _room_touches_wall(r, W, H, wall)]
    if not candidates:
        return None
    r = candidates[0]
    if wall == "north":
        dx, dy = r["x"] + r["width"] / 2, r["y"]
        dwall = "north"
    elif wall == "south":
        dx, dy = r["x"] + r["width"] / 2, r["y"] + r["height"]
        dwall = "south"
    elif wall == "east":
        dx, dy = r["x"] + r["width"], r["y"] + r["height"] / 2
        dwall = "east"
    else:  # west
        dx, dy = r["x"], r["y"] + r["height"] / 2
        dwall = "west"
    door = {
        "id": f"{r['id']}_entrance_door",
        "wall": dwall,
        "x": round(dx, 2),
        "y": round(dy, 2),
        "width": 3.0,
        "entrance": True,
    }
    r["doors"].append(door)
    return door


def _rooms_share_wall(a: Dict[str, Any], b: Dict[str, Any]) -> str | None:
    """Return the shared wall side ('north','south','east','west') if rooms
    are adjacent, else None."""
    eps = 0.1
    a_x1, a_y1, a_x2, a_y2 = a["x"], a["y"], a["x"] + a["width"], a["y"] + a["height"]
    b_x1, b_y1, b_x2, b_y2 = b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"]
    # a north of b (a.bottom == b.top)
    if abs(a_y2 - b_y1) < eps:
        overlap = min(a_x2, b_x2) - max(a_x1, b_x1)
        if overlap > 1.5:
            return "south"
    # a south of b (a.top == b.bottom)
    if abs(a_y1 - b_y2) < eps:
        overlap = min(a_x2, b_x2) - max(a_x1, b_x1)
        if overlap > 1.5:
            return "north"
    # a east of b (a.left == b.right)
    if abs(a_x2 - b_x1) < eps:
        overlap = min(a_y2, b_y2) - max(a_y1, b_y1)
        if overlap > 1.5:
            return "east"
    # a west of b (a.right == b.left)
    if abs(a_x1 - b_x2) < eps:
        overlap = min(a_y2, b_y2) - max(a_y1, b_y1)
        if overlap > 1.5:
            return "west"
    return None


def _add_internal_doors(rooms: List[Dict[str, Any]]) -> None:
    """Add internal doors between rooms that share a wall."""
    door_id = 1
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            a, b = rooms[i], rooms[j]
            if a["type"] == "staircase" or b["type"] == "staircase":
                continue
            shared = _rooms_share_wall(a, b)
            if shared is None:
                continue
            # Door on the shared wall, centered in the overlapping segment
            eps = 0.1
            a_x1, a_y1, a_x2, a_y2 = a["x"], a["y"], a["x"] + a["width"], a["y"] + a["height"]
            b_x1, b_y1, b_x2, b_y2 = b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"]
            if shared in ("south", "north"):
                cx = max(a_x1, b_x1)
                cw = min(a_x2, b_x2) - cx
                dx = cx + cw / 2
                dy = a_y2 if shared == "south" else a_y1
                dwall = shared
            else:
                cy = max(a_y1, b_y1)
                ch = min(a_y2, b_y2) - cy
                dy = cy + ch / 2
                dx = a_x2 if shared == "east" else a_x1
                dwall = shared
            a["doors"].append({
                "id": f"{a['id']}_int_door_{door_id}",
                "wall": dwall, "x": round(dx, 2), "y": round(dy, 2),
                "width": 3.0, "internal": True,
            })
            b["doors"].append({
                "id": f"{b['id']}_int_door_{door_id}",
                "wall": dwall, "x": round(dx, 2), "y": round(dy, 2),
                "width": 3.0, "internal": True,
            })
            door_id += 1


def _add_windows(rooms: List[Dict[str, Any]], W: float, H: float) -> None:
    """Add windows on exterior walls for habitable rooms."""
    for r in rooms:
        if r["type"] in ("staircase", "corridor"):
            continue
        # Determine which exterior walls this room touches
        touched = [w for w in ("north", "south", "east", "west")
                   if _room_touches_wall(r, W, H, w)]
        if not touched:
            continue
        # Prefer north/east walls for windows
        pref = [w for w in ("north", "east", "south", "west") if w in touched]
        wall = pref[0]
        if wall in ("north", "south"):
            dx = r["x"] + r["width"] / 2
            dy = r["y"] if wall == "north" else r["y"] + r["height"]
        else:
            dx = r["x"] if wall == "west" else r["x"] + r["width"]
            dy = r["y"] + r["height"] / 2
        r["windows"].append({
            "id": f"{r['id']}_win_ext",
            "wall": wall, "x": round(dx, 2), "y": round(dy, 2),
            "width": 3.0,
        })


def _add_doors_windows_to_floor(rooms: List[Dict[str, Any]], W: float, H: float,
                                entrance_dir: str, is_ground_floor: bool) -> None:
    """Add entrance door, internal doors, and windows to all rooms on a floor."""
    # Entrance door on exterior wall (ground floor only)
    if is_ground_floor:
        _add_entrance_door(rooms, W, H, entrance_dir)
    # Internal doors between rooms
    _add_internal_doors(rooms)
    # Windows on exterior walls
    _add_windows(rooms, W, H)


def _distribute_counts_across_floors(parsed: Dict[str, Any], floors: int) -> List[Dict[str, int]]:
    """Distribute requested rooms across floors meaningfully.

    Ground floor keeps the common areas (living + kitchen). Bedrooms are
    offered to upper floors first (one per floor, then any remainder goes to
    the ground floor), bathrooms follow the bedrooms, dining stays on the
    ground floor and balconies attach to upper-floor bedrooms. Every floor
    therefore keeps a purpose instead of duplicating the same layout.
    """
    bedrooms = int(parsed.get("bedrooms", 2))
    bathrooms = int(parsed.get("bathrooms", 2))
    kitchens = int(parsed.get("kitchens", 1))
    living = int(parsed.get("living_rooms", 1))
    dining = int(parsed.get("dining_rooms", 0))
    balconies = int(parsed.get("balconies", 0))

    plans: List[Dict[str, int]] = []
    for _ in range(floors):
        plans.append({"bedroom": 0, "bathroom": 0, "kitchen": 0,
                      "living_room": 0, "dining_room": 0, "balcony": 0})

    if floors == 1:
        plans[0] = {"bedroom": bedrooms, "bathroom": bathrooms, "kitchen": kitchens,
                    "living_room": living, "dining_room": dining, "balcony": balconies}
        return plans

    # Ground floor: common areas
    plans[0]["living_room"] = living
    plans[0]["kitchen"] = kitchens

    # Bedrooms: upper floors first, one per floor, then remainder to ground
    remaining = bedrooms
    idx = 1
    while remaining > 0 and idx < floors:
        plans[idx]["bedroom"] += 1
        remaining -= 1
        idx += 1
        if idx >= floors and remaining > 0:
            idx = 1
    plans[0]["bedroom"] += remaining

    # Bathrooms: one per floor that has a bedroom (upper floors first),
    # then ground, then any remainder to ground.
    remaining_b = bathrooms
    for i in range(1, floors):
        if remaining_b > 0 and plans[i]["bedroom"] > 0:
            plans[i]["bathroom"] += 1
            remaining_b -= 1
    if remaining_b > 0 and plans[0]["bedroom"] > 0:
        plans[0]["bathroom"] += 1
        remaining_b -= 1
    plans[0]["bathroom"] += remaining_b

    # Dining on ground with living
    plans[0]["dining_room"] = dining

    # Balconies attach to upper-floor bedrooms first
    remaining_bl = balconies
    for i in range(floors - 1, 0, -1):
        if remaining_bl > 0 and plans[i]["bedroom"] > 0:
            plans[i]["balcony"] += 1
            remaining_bl -= 1
    plans[0]["balcony"] += remaining_bl

    return plans


def _parsed_for_floor(parsed: Dict[str, Any], counts: Dict[str, int], budget_area: float) -> Dict[str, Any]:
    p = dict(parsed)
    p["bedrooms"] = int(counts.get("bedroom", 0))
    p["bathrooms"] = int(counts.get("bathroom", 0))
    p["kitchens"] = int(counts.get("kitchen", 0))
    p["balconies"] = int(counts.get("balcony", 0))
    p["living_rooms"] = int(counts.get("living_room", 0))
    p["dining_rooms"] = int(counts.get("dining_room", 0))
    p["total_area_sqft"] = float(budget_area)
    return p


def _staircase_room(floor_index: int, rect: Dict[str, float]) -> Dict[str, Any]:
    return {
        "id": f"stair_f{floor_index}",
        "type": "staircase",
        "label": "Staircase",
        "x": round(rect["x"], 2),
        "y": round(rect["y"], 2),
        "width": round(rect["width"], 2),
        "height": round(rect["height"], 2),
        "area": round(rect["width"] * rect["height"], 2),
        "target_area": round(rect["width"] * rect["height"], 2),
        "doors": [],
        "windows": [],
        "furniture": [],
        "lighting": [],
        "plumbing": [],
    }


def _assemble_layout(rooms: List[Dict[str, Any]], W: float, H: float, parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Common post-processing: doors/windows, furniture, lighting, plumbing,
    adjacency, orientation and metadata. Staircase rooms keep no openings or
    furniture/lighting fixtures."""
    actual_total = sum(r["area"] for r in rooms)
    orient = orientation_metadata(parsed.get("main_entrance_direction", "east"), W, H)
    adj = adjacency_from_geometry(rooms)

    non_stair = [r for r in rooms if r["type"] != "staircase"]
    furniture = generate_furniture(non_stair)
    lighting = generate_lighting(non_stair)
    plumbing_fixtures, plumbing_routes = generate_plumbing(rooms)

    doors = []
    windows = []
    for r in rooms:
        if r["type"] == "staircase":
            continue
        doors.extend(r["doors"])
        windows.extend(r["windows"])

    layout = {
        "width": W,
        "height": H,
        "total_area": round(actual_total, 2),
        "built_up_area": round(float(parsed.get("total_area_sqft", actual_total)), 2),
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
            "style": parsed.get("style", "modern"),
            "entrance_direction": parsed.get("main_entrance_direction", "east"),
            "parsed_input": parsed,
            "generation_notes": [
                f"Row-band tiled {len(rooms)} rooms across {W:.1f} x {H:.1f} ft footprint",
                f"Actual room area sum {actual_total:.1f} vs requested {float(parsed.get('total_area_sqft', 0)):.1f}",
                f"Adjacency pairs: {len(adj)}",
            ],
            "warnings": parsed.get("warnings", []),
        },
    }
    return layout


def _add_single_floor_entrance(layout: Dict[str, Any], entrance_dir: str) -> None:
    """Place the main entrance door on the exterior wall per facing direction,
    in the living room. Adds to both the room's doors and layout's doors."""
    W = layout["width"]; H = layout["height"]
    wall = _exterior_wall_for_direction(entrance_dir)
    # Find living room touching the entrance wall
    candidates = [r for r in layout["rooms"]
                  if r["type"] == "living_room" and _room_touches_wall(r, W, H, wall)]
    if not candidates:
        candidates = [r for r in layout["rooms"]
                      if r["type"] != "staircase" and _room_touches_wall(r, W, H, wall)]
    if not candidates:
        return
    r = candidates[0]
    if wall == "north":
        dx, dy = r["x"] + r["width"] / 2, r["y"]; dwall = "north"
    elif wall == "south":
        dx, dy = r["x"] + r["width"] / 2, r["y"] + r["height"]; dwall = "south"
    elif wall == "east":
        dx, dy = r["x"] + r["width"], r["y"] + r["height"] / 2; dwall = "east"
    else:
        dx, dy = r["x"], r["y"] + r["height"] / 2; dwall = "west"
    door = {
        "id": f"{r['id']}_entrance_door",
        "wall": dwall, "x": round(dx, 2), "y": round(dy, 2),
        "width": 3.0, "entrance": True,
    }
    r["doors"].append(door)
    layout["doors"].append(door)


def _finalize_single_floor(layout: Dict[str, Any], parsed: Dict[str, Any]) -> Dict[str, Any]:
    layout["floors"] = 1
    layout["floor_index"] = 0
    layout["active_floor"] = 0
    layout["staircase"] = None
    # Add main entrance door on exterior wall per facing direction
    _add_single_floor_entrance(layout, parsed.get("main_entrance_direction", "east"))
    floor_plan = {
        "floor_index": 0,
        "label": "Ground Floor",
        "width": layout["width"],
        "height": layout["height"],
        "rooms": layout["rooms"],
        "furniture": layout["furniture"],
        "lighting": layout["lighting"],
        "doors": layout["doors"],
        "windows": layout["windows"],
        "plumbing_fixtures": layout["plumbing_fixtures"],
        "plumbing_routes": layout["plumbing_routes"],
        "total_area": layout["total_area"],
        "staircase": None,
    }
    layout["floor_plans"] = [floor_plan]
    layout["metadata"]["generation_notes"].append("Single-floor residential layout (default)")
    layout["metadata"]["multi_floor"] = False
    return layout


def generate_floorplan(parsed: Dict[str, Any]) -> Dict[str, Any]:
    total_area = float(parsed["total_area_sqft"])
    entrance_dir = parsed.get("main_entrance_direction", "east")
    style = parsed.get("style", "modern")
    floors = max(1, int(parsed.get("floors", 1)))

    if floors == 1:
        # --- existing single-floor behaviour, preserved exactly ---
        area_map = _distribute_areas(parsed)
        rooms, footprint_w, footprint_h = _place_rooms_tiled(area_map, total_area, entrance_dir, style)
        layout = _assemble_layout(rooms, footprint_w, footprint_h, parsed)
        return _finalize_single_floor(layout, parsed)

    # --- multi-floor path ---
    # Common footprint for the whole building: sized from the full program so
    # every floor shares identical width/height and the staircase aligns.
    area_map = _distribute_areas(parsed)
    _, footprint_w, footprint_h = _place_rooms_tiled(area_map, total_area, entrance_dir, style)

    W = float(footprint_w)
    H_common = float(footprint_h)

    counts_per_floor = _distribute_counts_across_floors(parsed, floors)
    budget_per_floor = total_area / floors
    # Relax min dims for small per-floor budgets (multi-floor compact homes)
    min_dim_scale = 1.0
    if budget_per_floor < 300:
        min_dim_scale = 0.75

    # Grow the common footprint height until every floor's rooms fit above the
    # reserved staircase strip (bottom-right corner, height STAIR_DEPTH).
    # Use the same min_dim_scale as the actual placement so H_common matches.
    for _ in range(6):
        max_needed = STAIR_DEPTH
        for fi in range(floors):
            f_parsed = _parsed_for_floor(parsed, counts_per_floor[fi], budget_per_floor)
            f_area_map = _distribute_areas(f_parsed)
            _, h_used, _w_out = _place_floor_at_fixed_width(
                f_area_map, W, y0=STAIR_DEPTH, min_dim_scale=min_dim_scale)
            max_needed = max(max_needed, STAIR_DEPTH + h_used)
        if max_needed <= H_common:
            break
        H_common = max_needed + 1.0

    # Staircase: same rectangle on every floor -> vertically aligned stairwell.
    staircase = {
        "x": round(W - STAIR_WIDTH, 2),
        "y": 0.0,
        "width": STAIR_WIDTH,
        "height": STAIR_DEPTH,
        "story_height": STORY_HEIGHT,
        "connects_floors": list(range(floors)),
    }

    floor_plans: List[Dict[str, Any]] = []
    all_rooms: List[Dict[str, Any]] = []
    all_furniture: List[Dict[str, Any]] = []
    all_lighting: List[Dict[str, Any]] = []
    all_doors: List[Dict[str, Any]] = []
    all_windows: List[Dict[str, Any]] = []
    all_plumbing_fixtures: List[Dict[str, Any]] = []
    all_plumbing_routes: List[Dict[str, Any]] = []

    for fi in range(floors):
        # Relax min dims for small per-floor budgets (multi-floor compact homes)
        min_dim_scale = 1.0
        if budget_per_floor < 300:
            min_dim_scale = 0.75
        f_parsed = _parsed_for_floor(parsed, counts_per_floor[fi], budget_per_floor)
        f_area_map = _distribute_areas(f_parsed)
        rooms_f, h_used = _place_floor_with_openings(
            f_area_map, W, entrance_dir, is_ground_floor=(fi == 0),
            y0=STAIR_DEPTH, min_dim_scale=min_dim_scale)
        for r in rooms_f:
            r["floor"] = fi

        stair_room = _staircase_room(fi, staircase)
        floor_rooms = rooms_f + [stair_room]

        floor_layout = _assemble_layout(floor_rooms, W, H_common, f_parsed)

        floor_plan = {
            "floor_index": fi,
            "label": _floor_label(fi),
            "width": W,
            "height": H_common,
            "rooms": floor_layout["rooms"],
            "furniture": floor_layout["furniture"],
            "lighting": floor_layout["lighting"],
            "doors": floor_layout["doors"],
            "windows": floor_layout["windows"],
            "plumbing_fixtures": floor_layout["plumbing_fixtures"],
            "plumbing_routes": floor_layout["plumbing_routes"],
            "total_area": floor_layout["total_area"],
            "parsed": f_parsed,
            "staircase": dict(staircase),
        }
        floor_plans.append(floor_plan)

        # ALL floors' rooms go into layout["rooms"] so compliance/cost/GCN
        # see the complete building, not just the active floor.
        all_rooms.extend(floor_rooms)
        all_furniture.extend(floor_layout["furniture"])
        all_lighting.extend(floor_layout["lighting"])
        all_doors.extend(floor_layout["doors"])
        all_windows.extend(floor_layout["windows"])
        all_plumbing_fixtures.extend(floor_layout["plumbing_fixtures"])
        all_plumbing_routes.extend(floor_layout["plumbing_routes"])

    actual_total = sum(r["area"] for r in all_rooms)
    orient = orientation_metadata(entrance_dir, W, H_common)
    adj = adjacency_from_geometry(all_rooms)

    layout = {
        "width": W,
        "height": H_common,
        "total_area": round(actual_total, 2),
        "built_up_area": round(total_area, 2),
        "rooms": all_rooms,
        "furniture": all_furniture,
        "lighting": all_lighting,
        "plumbing_fixtures": all_plumbing_fixtures,
        "plumbing_routes": all_plumbing_routes,
        "doors": all_doors,
        "windows": all_windows,
        "orientation": orient,
        "adjacency": adj,
        "floors": floors,
        "floor_index": 0,
        "active_floor": 0,
        "floor_plans": floor_plans,
        "staircase": dict(staircase),
        "metadata": {
            "style": style,
            "entrance_direction": entrance_dir,
            "parsed_input": parsed,
            "generation_notes": [
                f"Multi-floor residential layout: {floors} floors across {W:.1f} x {H_common:.1f} ft footprint",
                f"Actual room area sum {actual_total:.1f} vs requested {total_area:.1f}",
                f"Staircase reserved at {staircase['x']}x{staircase['y']} ({STAIR_WIDTH}x{STAIR_DEPTH} ft) on every floor",
                f"Adjacency pairs: {len(adj)}",
            ],
            "warnings": parsed.get("warnings", []),
            "multi_floor": True,
        },
    }
    return layout
