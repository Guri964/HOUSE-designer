from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

@dataclass
class Room:
    id: str
    type: str
    label: str
    x: float
    y: float
    width: float
    height: float
    area: float
    doors: List[Dict[str, Any]] = field(default_factory=list)
    windows: List[Dict[str, Any]] = field(default_factory=list)
    furniture: List[Dict[str, Any]] = field(default_factory=list)
    lighting: List[Dict[str, Any]] = field(default_factory=list)
    plumbing: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class FurnitureItem:
    id: str
    type: str
    x: float
    y: float
    width: float
    height: float
    rotation: float = 0

@dataclass
class LightingFixture:
    id: str
    type: str
    x: float
    y: float
    room_id: str

@dataclass
class PlumbingFixture:
    id: str
    type: str
    x: float
    y: float
    room_id: str

@dataclass
class PlumbingRoute:
    id: str
    from_fixture: str
    to_fixture: str
    path: List[List[float]]
    kind: str

@dataclass
class Layout:
    width: float
    height: float
    total_area: float
    built_up_area: float
    rooms: List[Room]
    furniture: List[Dict[str, Any]]
    lighting: List[Dict[str, Any]]
    plumbing_fixtures: List[Dict[str, Any]]
    plumbing_routes: List[Dict[str, Any]]
    doors: List[Dict[str, Any]]
    windows: List[Dict[str, Any]]
    orientation: Dict[str, Any]
    adjacency: List[List[str]]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def validate_layout_dict(d: Dict[str, Any]) -> List[str]:
    errors = []
    if "rooms" not in d or not isinstance(d["rooms"], list):
        errors.append("rooms must be a list")
    if "width" not in d or "height" not in d:
        errors.append("width and height required")
    for r in d.get("rooms", []):
        if r.get("width", 0) <= 0 or r.get("height", 0) <= 0:
            errors.append(f"room {r.get('id','?')} has invalid dimensions")
    return errors
