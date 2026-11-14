from typing import Dict, List, Any, Tuple
import math

from ..config import ROOM_CATEGORY_TO_ID, BACKEND_TO_CLAUDE_ROOM_ID, CLAUDE_FEATURE_ORDER

def build_graph_features(layout: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy 14-dim features (8 one-hot + 6). Kept for fallback/baseline."""
    rooms = layout.get("rooms", [])
    n = len(rooms)
    if n == 0:
        return {"num_nodes": 0, "node_features": [], "edge_index": [], "edge_labels": [], "room_ids": []}
    width = layout.get("width", 40)
    height = layout.get("height", 40)
    max_area = max(r.get("area", 100) for r in rooms) if rooms else 200
    node_features = []
    room_ids = []
    id_to_idx = {r["id"]: i for i, r in enumerate(rooms)}
    for r in rooms:
        cat = r.get("type", "bedroom")
        cat_id = ROOM_CATEGORY_TO_ID.get(cat, 1)
        one_hot = [1.0 if i == cat_id else 0.0 for i in range(len(ROOM_CATEGORY_TO_ID))]
        area_norm = r.get("area", 100) / max_area
        w_norm = r.get("width", 10) / width if width else 0.5
        h_norm = r.get("height", 10) / height if height else 0.5
        x_norm = r.get("x", 0) / width if width else 0
        y_norm = r.get("y", 0) / height if height else 0
        aspect = r.get("width", 10) / max(r.get("height", 10), 0.1)
        aspect_norm = min(aspect / 2.5, 1.0)
        feats = one_hot + [area_norm, w_norm, h_norm, x_norm, y_norm, aspect_norm]
        node_features.append(feats)
        room_ids.append(r["id"])

    adjacency = layout.get("adjacency", [])
    edge_index: List[List[int]] = [[], []]
    for a_id, b_id in adjacency:
        if a_id in id_to_idx and b_id in id_to_idx:
            i, j = id_to_idx[a_id], id_to_idx[b_id]
            edge_index[0].append(i)
            edge_index[1].append(j)
            edge_index[0].append(j)
            edge_index[1].append(i)

    return {
        "num_nodes": n,
        "num_features": len(node_features[0]) if node_features else 0,
        "node_features": node_features,
        "edge_index": edge_index,
        "room_ids": room_ids,
        "id_to_idx": id_to_idx
    }

def build_graph_features_claude(layout: Dict[str, Any], feat_mean=None, feat_std=None) -> Dict[str, Any]:
    """
    Claude notebook 7-dim features:
    ["room_type", "width_norm", "height_norm", "area_norm", "aspect_ratio", "cx", "cy"]
    where:
      width_norm = width / 256 (via scaling)
      height_norm = height / 256
      area_norm = area / (256*256)
      cx = (x + width/2)/256, cy = (y + height/2)/256
    Then standardized: (x - mean)/std using feat_mean/std from gcn_config.json
    Room type is integer id per CLAUDE_ROOM_TYPE_MAP (0-13), not one-hot.
    """
    rooms = layout.get("rooms", [])
    n = len(rooms)
    if n == 0:
        return {"num_nodes": 0, "node_features": [], "edge_index": [[], []], "room_ids": []}
    # Use canvas 256 as in training. Our layout is in feet, we map via scaling.
    # Training boxes are pixel coords in 256x256 canvas. We emulate by treating layout
    # width/height as canvas size and normalizing accordingly.
    # Approach: factor = 256 / max(layout.width, layout.height) to map feet -> pixels, then normalize by 256.
    # Equivalent to width_norm = width / max_dim
    layout_w = layout.get("width", 40) or 40
    layout_h = layout.get("height", 40) or 40
    max_dim = max(layout_w, layout_h, 1.0)
    # For area, use 256*256 denominator after scaling: effective area_norm = (w*h)/(256*256) * (factor^2) = (w*h)/(max_dim^2)
    # So we can compute directly as w*h / (max_dim*max_dim) to keep scale comparable.
    node_features: List[List[float]] = []
    room_ids: List[str] = []
    id_to_idx = {r["id"]: i for i, r in enumerate(rooms)}
    for r in rooms:
        backend_type = r.get("type", "living_room")
        claude_type = BACKEND_TO_CLAUDE_ROOM_ID.get(backend_type, 0)
        # width/height in feet, convert to normalized as per Claude: width/256 etc. via scaling
        w = r.get("width", 10)
        h = r.get("height", 10)
        # Use max_dim method to map to 256 canvas
        w_norm = w / max_dim
        h_norm = h / max_dim
        area = r.get("area", w * h)
        a_norm = area / (max_dim * max_dim)
        aspect = w / (h + 1e-5)
        cx = (r.get("x", 0) + w / 2) / max_dim
        cy = (r.get("y", 0) + h / 2) / max_dim
        feats = [float(claude_type), float(w_norm), float(h_norm), float(a_norm), float(aspect), float(cx), float(cy)]
        # Standardize if mean/std provided
        if feat_mean is not None and feat_std is not None and len(feat_mean) == 7 and len(feat_std) == 7:
            feats = [(feats[i] - feat_mean[i]) / (feat_std[i] + 1e-8) for i in range(7)]
        node_features.append(feats)
        room_ids.append(r["id"])

    adjacency = layout.get("adjacency", [])
    edge_index: List[List[int]] = [[], []]
    for a_id, b_id in adjacency:
        if a_id in id_to_idx and b_id in id_to_idx:
            i, j = id_to_idx[a_id], id_to_idx[b_id]
            edge_index[0].append(i)
            edge_index[1].append(j)
            edge_index[0].append(j)
            edge_index[1].append(i)

    return {
        "num_nodes": n,
        "num_features": 7,
        "node_features": node_features,
        "edge_index": edge_index,
        "room_ids": room_ids,
        "id_to_idx": id_to_idx,
        "max_dim": max_dim
    }

def adjacency_matrix_from_edges(num_nodes: int, edge_index: List[List[int]]) -> List[List[int]]:
    mat = [[0]*num_nodes for _ in range(num_nodes)]
    for s, t in zip(edge_index[0], edge_index[1]):
        if 0 <= s < num_nodes and 0 <= t < num_nodes:
            mat[s][t] = 1
    return mat
