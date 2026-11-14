import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..config import (
    GCN_MODEL_PATH, GCN_CONFIG_PATH,
    GCN_MODEL_CANDIDATES, GCN_CONFIG_CANDIDATES,
    GCN_MODEL_PATH_LEGACY, GCN_CONFIG_PATH_LEGACY
)
from ..validation.graph_builder import build_graph_features, build_graph_features_claude
from .gcn_model import baseline_adjacency_score, baseline_classify, HAS_TORCH_GEOMETRIC

try:
    import torch
    HAS_TORCH = True
except Exception:
    torch = None
    HAS_TORCH = False

def _resolve_first_existing(candidates: List[str], env_path: str) -> Optional[str]:
    """Return first existing path from candidates + env override."""
    # env override has priority if it exists
    if env_path and os.path.exists(env_path):
        return env_path
    for p in candidates:
        if os.path.exists(p):
            return p
    # if nothing exists, return env_path as intended (for error messaging)
    return env_path if env_path else candidates[0] if candidates else None

class GCNInference:
    def __init__(self, model_path: str = GCN_MODEL_PATH, config_path: str = GCN_CONFIG_PATH):
        self.model_path = _resolve_first_existing(GCN_MODEL_CANDIDATES, model_path)
        self.config_path = _resolve_first_existing(GCN_CONFIG_CANDIDATES, config_path)
        # keep original for status
        self.requested_model_path = model_path
        self.requested_config_path = config_path
        self.model = None
        self.config = None
        self.feat_mean = None
        self.feat_std = None
        self.in_channels = 7
        self.hidden_channels = 128
        self.num_classes = 2
        self.dropout = 0.3
        self.is_claude_model = False
        self.device = "cpu"
        if HAS_TORCH and torch.cuda.is_available():
            self.device = "cuda"
        self.loaded = False
        self.artifact_status = self._check_artifacts()

    def _check_artifacts(self) -> Dict[str, Any]:
        model_path_resolved = self.model_path
        config_path_resolved = self.config_path
        model_exists = os.path.exists(model_path_resolved) if model_path_resolved else False
        config_exists = os.path.exists(config_path_resolved) if config_path_resolved else False
        cfg = None
        cfg_error = None
        feat_mean = None
        feat_std = None
        is_claude = False
        if config_exists:
            try:
                with open(config_path_resolved) as f:
                    cfg = json.load(f)
                self.config = cfg
                # Detect Claude config structure
                if "model" in cfg and "in_channels" in cfg["model"]:
                    is_claude = True
                    self.is_claude_model = True
                    self.in_channels = cfg["model"].get("in_channels", 7)
                    self.hidden_channels = cfg["model"].get("hidden_channels", 128)
                    self.num_classes = cfg["model"].get("num_classes", 2)
                    self.dropout = cfg["model"].get("dropout", 0.3)
                    norm = cfg.get("normalization", {})
                    feat_mean = norm.get("feat_mean")
                    feat_std = norm.get("feat_std")
                    self.feat_mean = feat_mean
                    self.feat_std = feat_std
                elif "in_dim" in cfg:
                    # Legacy
                    self.in_channels = cfg.get("in_dim", 14)
                    self.hidden_channels = cfg.get("hidden", 64)
                    self.num_classes = cfg.get("num_classes", 2)
                    self.is_claude_model = False
                else:
                    # Unknown, assume Claude if feat_mean present
                    if "normalization" in cfg:
                        is_claude = True
                        self.is_claude_model = True
                        norm = cfg.get("normalization", {})
                        feat_mean = norm.get("feat_mean")
                        feat_std = norm.get("feat_std")
                        self.feat_mean = feat_mean
                        self.feat_std = feat_std
            except Exception as e:
                cfg = {"error": str(e)}
                cfg_error = str(e)
        return {
            "model_path": model_path_resolved,
            "config_path": config_path_resolved,
            "requested_model_path": self.requested_model_path,
            "requested_config_path": self.requested_config_path,
            "candidates_model": GCN_MODEL_CANDIDATES,
            "candidates_config": GCN_CONFIG_CANDIDATES,
            "model_exists": model_exists,
            "config_exists": config_exists,
            "config": cfg,
            "config_error": cfg_error,
            "is_claude_model": is_claude,
            "feat_mean": feat_mean,
            "feat_std": feat_std,
            "has_torch": HAS_TORCH,
            "has_torch_geometric": HAS_TORCH_GEOMETRIC,
            "note": "Falling back to deterministic baseline when artifacts unavailable. Baseline is NOT presented as trained GCN; outputs are labeled accordingly."
        }

    def load(self) -> Dict[str, Any]:
        if self.loaded:
            return self.artifact_status
        self.artifact_status = self._check_artifacts()
        if not self.artifact_status["model_exists"] or not HAS_TORCH or not HAS_TORCH_GEOMETRIC:
            self.loaded = True
            return self.artifact_status
        try:
            # Decide which model class to instantiate based on config
            is_claude = self.artifact_status.get("is_claude_model", False) or self.is_claude_model
            # Also infer from in_channels
            if is_claude or self.in_channels == 7:
                from .gcn_model import _ClaudeGCN
                self.model = _ClaudeGCN(
                    in_channels=self.in_channels,
                    hidden_channels=self.hidden_channels,
                    num_classes=self.num_classes,
                    dropout=self.dropout
                )
                self.is_claude_model = True
            else:
                from .gcn_model import _GCNNet, IN_FEATURES
                in_dim = self.config.get("in_dim", IN_FEATURES) if self.config else IN_FEATURES
                hidden = self.config.get("hidden", 64) if self.config else 64
                num_classes = self.config.get("num_classes", 2) if self.config else 2
                self.model = _GCNNet(in_dim, hidden, num_classes)
                self.is_claude_model = False

            state = torch.load(self.model_path, map_location="cpu")
            # Handle checkpoint dict variants
            if isinstance(state, dict) and "model_state" in state:
                state = state["model_state"]
            elif isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]
            # Remove unexpected keys if needed (e.g., if saved with different prefix)
            self.model.load_state_dict(state, strict=False)
            self.model.eval()
            if self.device == "cuda":
                self.model.to(self.device)
            self.artifact_status["model_loaded"] = True
            self.artifact_status["in_channels"] = self.in_channels
            self.artifact_status["hidden_channels"] = self.hidden_channels
            self.artifact_status["is_claude_model"] = self.is_claude_model
        except Exception as e:
            import traceback
            self.artifact_status["model_loaded"] = False
            self.artifact_status["load_error"] = str(e)
            self.artifact_status["traceback"] = traceback.format_exc()[:1200]
            self.model = None
        self.loaded = True
        return self.artifact_status

    def predict(self, layout: Dict[str, Any]) -> Dict[str, Any]:
        self.load()
        if self.model is not None and HAS_TORCH and self.artifact_status.get("model_loaded"):
            try:
                # Choose graph builder based on model type
                if self.is_claude_model:
                    graph = build_graph_features_claude(layout, feat_mean=self.feat_mean, feat_std=self.feat_std)
                else:
                    graph = build_graph_features(layout)
                if graph["num_nodes"] == 0:
                    return {"score": 0.0, "label": 0, "source": "gcn_trained", "probs": [0.5, 0.5], "detail": "empty layout"}
                x = torch.tensor(graph["node_features"], dtype=torch.float32, device=self.device if self.device=="cpu" else "cpu")
                # Move to device after creation
                if self.device != "cpu":
                    x = x.to(self.device)
                edge_index = torch.tensor(graph["edge_index"], dtype=torch.long) if graph["edge_index"][0] else torch.empty((2, 0), dtype=torch.long)
                if edge_index.numel() == 0:
                    edge_index = torch.tensor([[i for i in range(graph["num_nodes"])], [i for i in range(graph["num_nodes"])]], dtype=torch.long)
                if self.device != "cpu":
                    edge_index = edge_index.to(self.device)
                with torch.no_grad():
                    # Both models accept (x, edge_index, batch) or (x, edge_index, batch) where batch is optional
                    # Create batch tensor
                    batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device if hasattr(x, 'device') else self.device)
                    if self.is_claude_model:
                        logits = self.model(x, edge_index, batch)
                    else:
                        logits, h, g = self.model(x, edge_index, batch)
                    # logits shape [1,2] or [2]
                    if logits.dim() == 1:
                        logits = logits.unsqueeze(0)
                    probs = torch.softmax(logits, dim=-1).cpu().numpy().tolist()[0]
                    if isinstance(probs, float):
                        probs = [1 - probs, probs]
                    score = float(probs[1]) if len(probs) > 1 else float(probs[0])
                    label = int(score >= 0.5)
                    # Map to new label names for Claude model
                    label_name = "Compliant" if label == 1 else "Partial"
                    return {
                        "score": round(score, 3),
                        "label": label,
                        "label_name": label_name,
                        "probs": [round(float(p), 3) for p in probs],
                        "source": "gcn_trained_claude" if self.is_claude_model else "gcn_trained",
                        "num_nodes": graph["num_nodes"],
                        "num_edges": len(graph["edge_index"][0]) // 2 if graph["edge_index"][0] else 0,
                        "is_claude_model": self.is_claude_model,
                        "in_channels": self.in_channels
                    }
            except Exception as e:
                import traceback
                base = baseline_classify(layout)
                base["source"] = "baseline_fallback"
                base["error"] = str(e)
                base["traceback"] = traceback.format_exc()[:800]
                return base
        else:
            base = baseline_classify(layout)
            base["source"] = "baseline" if not self.artifact_status.get("model_loaded") else "baseline_fallback"
            if not self.artifact_status.get("model_exists"):
                base["note"] = "Trained GCN artifacts not found; using deterministic adjacency baseline. Place gcn_model.pth + gcn_config.json per checklist for learned inference."
                base["expected_paths"] = {
                    "model_candidates": GCN_MODEL_CANDIDATES,
                    "config_candidates": GCN_CONFIG_CANDIDATES
                }
            return base

    def status(self) -> Dict[str, Any]:
        self.load()
        s = dict(self.artifact_status)
        s["loaded"] = self.loaded
        s["inference_ready"] = True
        s["inference_mode"] = "gcn_trained_claude" if s.get("model_loaded") and s.get("is_claude_model") else ("gcn_trained" if s.get("model_loaded") else "baseline")
        s["device"] = self.device
        return s
