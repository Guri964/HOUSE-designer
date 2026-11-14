from typing import List, Dict, Tuple, Optional

def rects_overlap(a: Dict, b: Dict, pad: float = 0.0) -> bool:
    return not (a["x"] + a["width"] + pad <= b["x"] or b["x"] + b["width"] + pad <= a["x"] or a["y"] + a["height"] + pad <= b["y"] or b["y"] + b["height"] + pad <= a["y"])

def rect_area(r: Dict) -> float:
    return r["width"] * r["height"]

def wall_segments(rooms: List[Dict]) -> List[Dict]:
    segs = []
    for r in rooms:
        x, y, w, h = r["x"], r["y"], r["width"], r["height"]
        segs.append({"x1": x, "y1": y, "x2": x + w, "y2": y})
        segs.append({"x1": x + w, "y1": y, "x2": x + w, "y2": y + h})
        segs.append({"x1": x + w, "y1": y + h, "x2": x, "y2": y + h})
        segs.append({"x1": x, "y1": y + h, "x2": x, "y2": y})
    return segs

def adjacency_from_geometry(rooms: List[Dict], tol: float = 0.6) -> List[List[str]]:
    adj = []
    for i, a in enumerate(rooms):
        for j, b in enumerate(rooms):
            if j <= i:
                continue
            # check if share edge within tolerance
            a_x1, a_y1, a_x2, a_y2 = a["x"], a["y"], a["x"] + a["width"], a["y"] + a["height"]
            b_x1, b_y1, b_x2, b_y2 = b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"]
            # horizontal adjacency
            horiz = abs(a_x2 - b_x1) < tol or abs(b_x2 - a_x1) < tol
            vert_overlap = min(a_y2, b_y2) - max(a_y1, b_y1) > 1.5
            # vertical adjacency
            vert = abs(a_y2 - b_y1) < tol or abs(b_y2 - a_y1) < tol
            horiz_overlap = min(a_x2, b_x2) - max(a_x1, b_x1) > 1.5
            if (horiz and vert_overlap) or (vert and horiz_overlap):
                adj.append([a["id"], b["id"]])
    return adj

def bounding_box(rooms: List[Dict]) -> Tuple[float, float, float, float]:
    if not rooms:
        return (0, 0, 0, 0)
    min_x = min(r["x"] for r in rooms)
    min_y = min(r["y"] for r in rooms)
    max_x = max(r["x"] + r["width"] for r in rooms)
    max_y = max(r["y"] + r["height"] for r in rooms)
    return (min_x, min_y, max_x, max_y)

def scale_to_area(rooms: List[Dict], target_area: float) -> List[Dict]:
    current = sum(r["width"] * r["height"] for r in rooms)
    if current <= 0:
        return rooms
    ratio = (target_area / current) ** 0.5
    # scale but keep relative positions
    for r in rooms:
        r["x"] *= ratio
        r["y"] *= ratio
        r["width"] *= ratio
        r["height"] *= ratio
        r["area"] = r["width"] * r["height"]
    return rooms
