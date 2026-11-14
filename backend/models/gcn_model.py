from typing import Dict, Any, List
import math

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.nn import GCNConv, global_mean_pool
    HAS_TORCH_GEOMETRIC = True
except Exception:
    torch = None
    nn = None
    HAS_TORCH_GEOMETRIC = False

# Legacy 14-dim (8 one-hot + 6) for fallback
ROOM_CATEGORIES_LEN = 8
FEAT_EXTRA = 6
IN_FEATURES = ROOM_CATEGORIES_LEN + FEAT_EXTRA

# Claude model constants
CLAUDE_IN_CHANNELS = 7
CLAUDE_HIDDEN_CHANNELS = 128
CLAUDE_NUM_CLASSES = 2

class HouseGCN:
    def __init__(self, in_dim: int = IN_FEATURES, hidden: int = 64, num_classes: int = 2):
        self.in_dim = in_dim
        self.hidden = hidden
        self.num_classes = num_classes
        self.model = None
        self.is_loaded = False
        if HAS_TORCH_GEOMETRIC and torch is not None:
            try:
                self.model = _GCNNet(in_dim, hidden, num_classes)
            except Exception:
                self.model = None

    def summary(self) -> Dict[str, Any]:
        return {
            "in_dim": self.in_dim,
            "hidden": self.hidden,
            "num_classes": self.num_classes,
            "has_torch_geometric": HAS_TORCH_GEOMETRIC,
            "model_created": self.model is not None
        }

if HAS_TORCH_GEOMETRIC and torch is not None:
    class _GCNNet(nn.Module):
        def __init__(self, in_dim, hidden, num_classes):
            super().__init__()
            self.conv1 = GCNConv(in_dim, hidden)
            self.conv2 = GCNConv(hidden, hidden)
            self.conv3 = GCNConv(hidden, hidden)
            self.lin = nn.Linear(hidden, hidden)
            self.classifier = nn.Linear(hidden, num_classes)
            self.edge_predictor = nn.Sequential(
                nn.Linear(hidden * 2, hidden),
                nn.ReLU(),
                nn.Linear(hidden, 1)
            )
            self.dropout = nn.Dropout(0.25)

        def forward(self, x, edge_index, batch=None):
            if batch is None:
                batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device)
            h = self.conv1(x, edge_index)
            h = F.relu(h)
            h = self.dropout(h)
            h = self.conv2(h, edge_index)
            h = F.relu(h)
            h = self.dropout(h)
            h = self.conv3(h, edge_index)
            h = F.relu(h)
            g = global_mean_pool(h, batch)
            g = F.relu(self.lin(g))
            out = self.classifier(g)
            return out, h, g

        def predict_adjacency(self, h, edge_candidates):
            if edge_candidates.size(1) == 0:
                return torch.empty(0)
            src = h[edge_candidates[0]]
            dst = h[edge_candidates[1]]
            pair = torch.cat([src, dst], dim=-1)
            logits = self.edge_predictor(pair).squeeze(-1)
            return torch.sigmoid(logits)

    class _ClaudeGCN(nn.Module):
        """
        Exact architecture from Claude notebook:
        GCN(7->128) -> BN -> ReLU -> Dropout 0.3
        GCN(128->128) -> BN -> ReLU -> Dropout
        GCN(128->64) -> BN -> ReLU
        global_mean_pool
        FC 64->64 -> ReLU -> Dropout
        FC 64->2
        """
        def __init__(self, in_channels=7, hidden_channels=128, num_classes=2, dropout=0.3):
            super().__init__()
            self.conv1 = GCNConv(in_channels, hidden_channels)
            self.conv2 = GCNConv(hidden_channels, hidden_channels)
            self.conv3 = GCNConv(hidden_channels, hidden_channels // 2)
            self.bn1 = nn.BatchNorm1d(hidden_channels)
            self.bn2 = nn.BatchNorm1d(hidden_channels)
            self.bn3 = nn.BatchNorm1d(hidden_channels // 2)
            self.fc1 = nn.Linear(hidden_channels // 2, 64)
            self.fc2 = nn.Linear(64, num_classes)
            self.drop = nn.Dropout(p=dropout)

        def forward(self, x, edge_index, batch=None):
            if batch is None:
                batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device)
            x = self.conv1(x, edge_index)
            x = self.bn1(x)
            x = F.relu(x)
            x = self.drop(x)
            x = self.conv2(x, edge_index)
            x = self.bn2(x)
            x = F.relu(x)
            x = self.drop(x)
            x = self.conv3(x, edge_index)
            x = self.bn3(x)
            x = F.relu(x)
            x = global_mean_pool(x, batch)
            x = self.fc1(x)
            x = F.relu(x)
            x = self.drop(x)
            x = self.fc2(x)
            return x

    def adjacency_accuracy_edge_logits():
        return True
else:
    class _GCNNet:
        pass
    class _ClaudeGCN:
        pass

# Deterministic baseline scorer (no torch) mimics GCN behavior for development
def baseline_adjacency_score(layout: Dict[str, Any]) -> float:
    rooms = layout.get("rooms", [])
    adj = layout.get("adjacency", [])
    adj_set = set(tuple(sorted(p)) for p in adj)
    score = 0.52
    type_to_ids = {}
    for r in rooms:
        type_to_ids.setdefault(r["type"], []).append(r["id"])
    kitchen_ids = type_to_ids.get("kitchen", [])
    living_ids = type_to_ids.get("living_room", [])
    dining_ids = type_to_ids.get("dining_room", [])
    bath_ids = type_to_ids.get("bathroom", [])
    balcony_ids = type_to_ids.get("balcony", [])
    bedroom_ids = type_to_ids.get("bedroom", [])
    if kitchen_ids and (living_ids or dining_ids):
        if any(tuple(sorted([k, l])) in adj_set for k in kitchen_ids for l in (living_ids + dining_ids)):
            score += 0.18
        else:
            score -= 0.10
    if balcony_ids:
        if any(tuple(sorted([b, x])) in adj_set for b in balcony_ids for x in (bedroom_ids + living_ids)):
            score += 0.10
        else:
            score -= 0.08
    if bedroom_ids and bath_ids:
        near = sum(1 for bed in bedroom_ids if any(tuple(sorted([bed, bath])) in adj_set for bath in bath_ids))
        score += 0.07 * near
    if adj and len(rooms) > 2:
        neighbors = {r["id"]: set() for r in rooms}
        for a, b in adj:
            if a in neighbors and b in neighbors:
                neighbors[a].add(b)
                neighbors[b].add(a)
        visited = set()
        if rooms:
            stack = [rooms[0]["id"]]
            visited.add(rooms[0]["id"])
            q = [rooms[0]["id"]]
            while q:
                cur = q.pop(0)
                for nb in neighbors[cur]:
                    if nb not in visited:
                        visited.add(nb)
                        q.append(nb)
            if len(visited) == len(rooms):
                score += 0.10
            elif len(visited) >= len(rooms) - 1:
                score += 0.04
            else:
                score -= 0.08
    has_overlap = False
    for i in range(len(rooms)):
        for j in range(i+1, len(rooms)):
            a, b = rooms[i], rooms[j]
            if not (a["x"] + a["width"] <= b["x"] + 0.1 or b["x"] + b["width"] <= a["x"] + 0.1 or a["y"] + a["height"] <= b["y"] + 0.1 or b["y"] + b["height"] <= a["y"] + 0.1):
                has_overlap = True
    if has_overlap:
        score -= 0.20
    total = sum(r.get("area", 0) for r in rooms)
    score = max(0.05, min(0.98, score))
    h = hash(tuple(sorted(r["id"] for r in rooms))) % 100
    score = min(0.97, max(0.30, score + (h - 50) * 0.0006))
    return round(float(score), 3)

def baseline_classify(layout: Dict[str, Any]) -> Dict[str, Any]:
    score = baseline_adjacency_score(layout)
    label = 1 if score >= 0.5 else 0
    return {"score": score, "label": label, "probs": [round(1 - score, 3), round(score, 3)]}
