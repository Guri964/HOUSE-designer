from typing import Dict, List, Any, Tuple
from ..config import COMPLIANCE_THRESHOLDS, MIN_ROOM_DIMS
from .graph_builder import build_graph_features

def check_room_counts(parsed: Dict[str, Any], layout: Dict[str, Any]) -> Dict[str, Any]:
    rooms = layout.get("rooms", [])
    type_counts = {}
    for r in rooms:
        type_counts[r["type"]] = type_counts.get(r["type"], 0) + 1
    checks = []
    # bedrooms
    exp_bed = int(parsed.get("bedrooms", 2))
    act_bed = type_counts.get("bedroom", 0)
    checks.append({
        "id": "bedroom_count",
        "label": f"Bedrooms: expected {exp_bed}, got {act_bed}",
        "passed": act_bed == exp_bed,
        "severity": "hard",
        "weight": 0.20
    })
    exp_bath = int(parsed.get("bathrooms", 2))
    act_bath = type_counts.get("bathroom", 0)
    checks.append({
        "id": "bathroom_count",
        "label": f"Bathrooms: expected {exp_bath}, got {act_bath}",
        "passed": act_bath == exp_bath,
        "severity": "hard",
        "weight": 0.15
    })
    # kitchen
    exp_k = int(parsed.get("kitchens", 1))
    act_k = type_counts.get("kitchen", 0)
    checks.append({
        "id": "kitchen_count",
        "label": f"Kitchen: expected {exp_k}, got {act_k}",
        "passed": act_k == exp_k,
        "severity": "hard",
        "weight": 0.10
    })
    # balcony if requested
    exp_bal = int(parsed.get("balconies", 0))
    act_bal = type_counts.get("balcony", 0)
    if exp_bal > 0:
        checks.append({
            "id": "balcony_count",
            "label": f"Balcony: expected {exp_bal}, got {act_bal}",
            "passed": act_bal >= exp_bal,
            "severity": "soft",
            "weight": 0.05
        })
    # living
    checks.append({
        "id": "living_present",
        "label": "Living room present",
        "passed": type_counts.get("living_room", 0) >= 1,
        "severity": "hard",
        "weight": 0.10
    })
    return {"checks": checks, "type_counts": type_counts}

def check_areas(layout: Dict[str, Any], parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks = []
    rooms = layout.get("rooms", [])
    total = sum(r.get("area", 0) for r in rooms)
    requested = float(parsed.get("total_area_sqft", total))
    tolerance = requested * 0.15
    diff = abs(total - requested)
    checks.append({
        "id": "total_area",
        "label": f"Total area {total:.1f} sqft vs requested {requested:.0f} (tolerance {tolerance:.0f})",
        "passed": diff <= tolerance,
        "severity": "soft",
        "weight": 0.10
    })
    # per-room min dimensions
    for r in rooms:
        min_w, min_h = MIN_ROOM_DIMS.get(r["type"], (6, 6))
        passes = r["width"] >= min_w - 0.5 and r["height"] >= min_h - 0.5
        # allow rotation
        passes = passes or (r["width"] >= min_h - 0.5 and r["height"] >= min_w - 0.5)
        checks.append({
            "id": f"min_dims_{r['id']}",
            "label": f"{r['label']}: {r['width']}x{r['height']} ft >= {min_w}x{min_h}",
            "passed": passes,
            "severity": "hard",
            "weight": 0.02
        })
    return checks

def check_geometry(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks = []
    rooms = layout.get("rooms", [])
    # overlap check
    has_overlap = False
    overlapping_pairs = []
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            a, b = rooms[i], rooms[j]
            overlap = not (a["x"] + a["width"] <= b["x"] + 0.1 or b["x"] + b["width"] <= a["x"] + 0.1 or a["y"] + a["height"] <= b["y"] + 0.1 or b["y"] + b["height"] <= a["y"] + 0.1)
            if overlap:
                has_overlap = True
                overlapping_pairs.append(f"{a['label']} ↔ {b['label']}")
    checks.append({
        "id": "no_overlap",
        "label": "No overlapping rooms" + (f" — overlaps: {', '.join(overlapping_pairs)}" if has_overlap else ""),
        "passed": not has_overlap,
        "severity": "hard",
        "weight": 0.15
    })
    # connectivity: check graph connectivity via adjacency
    adj = layout.get("adjacency", [])
    # build adjacency set
    if rooms:
        # BFS
        id_to_neighbors = {r["id"]: set() for r in rooms}
        for a, b in adj:
            if a in id_to_neighbors and b in id_to_neighbors:
                id_to_neighbors[a].add(b)
                id_to_neighbors[b].add(a)
        visited = set()
        stack = [rooms[0]["id"]]
        visited.add(rooms[0]["id"])
        queue = [rooms[0]["id"]]
        while queue:
            cur = queue.pop(0)
            for nb in id_to_neighbors.get(cur, []):
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        connected = len(visited) == len(rooms)
        # but also allow isolated balcony with single connection optional? We'll be strict
        checks.append({
            "id": "connectivity",
            "label": f"Room connectivity: {len(visited)}/{len(rooms)} rooms reachable",
            "passed": connected or len(visited) >= len(rooms) - 1,
            "severity": "soft",
            "weight": 0.05
        })
    # boundary
    width = layout.get("width", 0)
    height = layout.get("height", 0)
    out_of_bounds = any(r["x"] < -0.1 or r["y"] < -0.1 or r["x"] + r["width"] > width + 0.5 or r["y"] + r["height"] > height + 0.5 for r in rooms)
    checks.append({
        "id": "within_bounds",
        "label": f"Rooms within footprint {width:.1f}×{height:.1f} ft",
        "passed": not out_of_bounds,
        "severity": "hard",
        "weight": 0.05
    })
    return checks

def check_adjacency_rules(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks = []
    rooms = layout.get("rooms", [])
    adj = layout.get("adjacency", [])
    adj_set = set(tuple(sorted(p)) for p in adj)
    type_to_ids = {}
    for r in rooms:
        type_to_ids.setdefault(r["type"], []).append(r["id"])

    # kitchen adjacent to dining or living preferred
    kitchen_ids = type_to_ids.get("kitchen", [])
    living_ids = set(type_to_ids.get("living_room", []))
    dining_ids = set(type_to_ids.get("dining_room", []))
    if kitchen_ids:
        kitchen_adjacent_to_living_or_dining = any(
            any(tuple(sorted([k, l])) in adj_set for l in (living_ids | dining_ids)) for k in kitchen_ids
        )
        checks.append({
            "id": "kitchen_adjacency",
            "label": "Kitchen adjacent to Living/Dining",
            "passed": kitchen_adjacent_to_living_or_dining or len(living_ids | dining_ids) == 0,
            "severity": "soft",
            "weight": 0.04
        })
    # bathroom not directly adjacent to kitchen (hygiene) – soft rule
    bath_ids = type_to_ids.get("bathroom", [])
    if bath_ids and kitchen_ids:
        bath_kitchen_adj = any(tuple(sorted([b, k])) in adj_set for b in bath_ids for k in kitchen_ids)
        checks.append({
            "id": "bathroom_kitchen_separation",
            "label": "Bathroom separated from Kitchen",
            "passed": not bath_kitchen_adj,
            "severity": "soft",
            "weight": 0.03
        })
    # bedrooms clustered but not all isolated – at least one bedroom adjacent to bathroom or corridor
    if type_to_ids.get("bedroom"):
        bedroom_adjacent = any(
            any(tuple(sorted([bed, other])) in adj_set for other in (bath_ids + list(living_ids) + type_to_ids.get("corridor", [])))
            for bed in type_to_ids["bedroom"]
        )
        checks.append({
            "id": "bedroom_connectivity",
            "label": "Bedrooms connected to Living/Bathroom/Corridor",
            "passed": bedroom_adjacent,
            "severity": "soft",
            "weight": 0.04
        })
    # balcony attached to living or bedroom
    balcony_ids = type_to_ids.get("balcony", [])
    if balcony_ids:
        balcony_attached = any(
            any(tuple(sorted([bal, other])) in adj_set for other in (type_to_ids.get("bedroom", []) + type_to_ids.get("living_room", [])))
            for bal in balcony_ids
        )
        checks.append({
            "id": "balcony_attachment",
            "label": "Balcony attached to Bedroom or Living",
            "passed": balcony_attached,
            "severity": "soft",
            "weight": 0.03
        })
    return checks

def check_furniture_clearance(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks = []
    for r in layout.get("rooms", []):
        fur = r.get("furniture", [])
        # check no furniture outside room
        outside = any(f["x"] < r["x"] - 0.2 or f["y"] < r["y"] - 0.2 or f["x"] + f["width"] > r["x"] + r["width"] + 0.2 or f["y"] + f["height"] > r["y"] + r["height"] + 0.2 for f in fur)
        # overlap among furniture
        overlap = False
        for i in range(len(fur)):
            for j in range(i + 1, len(fur)):
                a, b = fur[i], fur[j]
                if not (a["x"] + a["width"] <= b["x"] - 0.4 or b["x"] + b["width"] <= a["x"] - 0.4 or a["y"] + a["height"] <= b["y"] - 0.4 or b["y"] + b["height"] <= a["y"] - 0.4):
                    overlap = True
        checks.append({
            "id": f"furniture_{r['id']}",
            "label": f"{r['label']} furniture valid ({len(fur)} items)",
            "passed": not outside and not overlap,
            "severity": "soft",
            "weight": 0.01
        })
    return checks

def compute_compliance_score(all_checks: List[Dict[str, Any]], gcn_score: float = None) -> Tuple[float, str]:
    total_weight = sum(c.get("weight", 0) for c in all_checks)
    passed_weight = sum(c.get("weight", 0) for c in all_checks if c.get("passed"))
    rule_score = passed_weight / total_weight if total_weight > 0 else 1.0
    # combine with GCN if available: weighted 0.7 rule + 0.3 gcn
    if gcn_score is not None:
        final = 0.68 * rule_score + 0.32 * float(gcn_score)
    else:
        final = rule_score
    final = max(0.0, min(1.0, final))
    if final >= COMPLIANCE_THRESHOLDS["fully_compliant"]:
        status = "FULLY_COMPLIANT"
    elif final >= COMPLIANCE_THRESHOLDS["partially_compliant"]:
        status = "PARTIALLY_COMPLIANT"
    else:
        status = "NON_COMPLIANT"
    return round(final, 3), status

def run_compliance(layout: Dict[str, Any], parsed: Dict[str, Any], gcn_result: Dict[str, Any] = None) -> Dict[str, Any]:
    rc = check_room_counts(parsed, layout)
    area_checks = check_areas(layout, parsed)
    geom_checks = check_geometry(layout)
    adj_checks = check_adjacency_rules(layout)
    fur_checks = check_furniture_clearance(layout)

    all_checks = rc["checks"] + area_checks + geom_checks + adj_checks + fur_checks

    gcn_score = None
    if gcn_result and "score" in gcn_result:
        gcn_score = gcn_result["score"]

    score, status = compute_compliance_score(all_checks, gcn_score)

    passed = [c for c in all_checks if c["passed"]]
    failed = [c for c in all_checks if not c["passed"] and c["severity"] == "hard"]
    warnings = [c for c in all_checks if not c["passed"] and c["severity"] == "soft"]

    # add orientation warning if mismatch
    orientation = layout.get("orientation", {})
    if parsed.get("main_entrance_direction") and orientation.get("requested_direction"):
        if parsed["main_entrance_direction"] != orientation["requested_direction"]:
            warnings.append({"id": "orientation_mismatch", "label": f"Requested {parsed['main_entrance_direction']} but got {orientation['requested_direction']}", "passed": False, "severity": "soft", "weight": 0})

    suggestions = []
    for c in failed:
        suggestions.append(f"Fix: {c['label']}")
    for c in warnings:
        suggestions.append(f"Consider: {c['label']}")

    # hard failures force non-compliant if critical
    hard_fail_weight = sum(c["weight"] for c in failed)
    if hard_fail_weight > 0.25 and status == "FULLY_COMPLIANT":
        status = "PARTIALLY_COMPLIANT"
    if any(c["id"] == "no_overlap" and not c["passed"] for c in all_checks):
        score = min(score, 0.55)
        status = "NON_COMPLIANT" if score < 0.60 else "PARTIALLY_COMPLIANT"

    return {
        "score": score,
        "status": status,
        "status_label": status.replace("_", " ").title(),
        "gcn_score": gcn_score,
        "rule_score": round(sum(c["weight"] for c in all_checks if c["passed"]) / max(sum(c["weight"] for c in all_checks), 1e-6), 3),
        "checks": all_checks,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "suggestions": suggestions,
        "type_counts": rc["type_counts"]
    }
