import re
from typing import Dict, Any, List

try:
    import spacy
    _nlp = None
    def get_nlp():
        global _nlp
        if _nlp is None:
            try:
                _nlp = spacy.load("en_core_web_sm")
            except OSError:
                _nlp = spacy.blank("en")
        return _nlp
except ImportError:
    spacy = None
    def get_nlp():
        return None

BHKS = {
    "1bhk": 1, "2bhk": 2, "3bhk": 3, "4bhk": 4, "5bhk": 5,
    "1 bhk": 1, "2 bhk": 2, "3 bhk": 3, "4 bhk": 4
}

ROOM_SYNONYMS = {
    "bedroom": ["bedroom", "bed room", "bedrooms", "bhk", "master bedroom"],
    "bathroom": ["bathroom", "bathrooms", "bath", "washroom", "toilet"],
    "kitchen": ["kitchen", "kitchens", "open kitchen", "closed kitchen"],
    "living_room": ["living room", "living", "hall", "drawing room"],
    "balcony": ["balcony", "balconies", "terrace", "verandah", "porch"],
    "dining_room": ["dining", "dining room"]
}

STYLE_KEYWORDS = ["modern", "traditional", "minimal", "minimalist", "luxury", "contemporary", "classic"]

DIRECTION_MAP = {
    "east": "east",
    "west": "west",
    "north": "north",
    "south": "south",
    "east facing": "east",
    "west facing": "west",
    "north facing": "north",
    "south facing": "south",
    "east-facing": "east",
    "north-east": "north_east",
    "north east": "north_east",
    "northwest": "north_west",
    "south-east": "south_east",
    "south-west": "south_west"
}

def extract_bhk(text: str) -> int:
    t = text.lower()
    for k, v in BHKS.items():
        if k in t:
            return v
    m = re.search(r"(\d)\s*bhk", t)
    if m:
        try:
            return int(m.group(1))
        except:
            pass
    m = re.search(r"(\d)\s*bedrooms?", t)
    if m:
        try:
            return int(m.group(1))
        except:
            pass
    return 0

def extract_area(text: str) -> float:
    t = text.lower().replace(",", "")
    m = re.search(r"(\d{3,5})\s*(sq\.?\s*ft|sqft|square feet|sq feet|sq\. ft)", t)
    if m:
        try:
            return float(m.group(1))
        except:
            pass
    m = re.search(r"(\d{3,5})\s*(sqm|sq m|square meter)", t)
    if m:
        try:
            return float(m.group(1)) * 10.7639
        except:
            pass
    return 0

def extract_counts(text: str) -> Dict[str, int]:
    t = text.lower()
    counts: Dict[str, int] = {}
    bhk = extract_bhk(t)
    if bhk:
        counts["bedroom"] = bhk
    m = re.search(r"(\d)\s*bathrooms?", t)
    if m:
        counts["bathroom"] = int(m.group(1))
    else:
        if "2 bathrooms" in t:
            counts["bathroom"] = 2
        elif "3 bathrooms" in t:
            counts["bathroom"] = 3
        elif "1 bathroom" in t:
            counts["bathroom"] = 1
    m = re.search(r"(\d)\s*balcon(?:y|ies)", t)
    if m:
        counts["balcony"] = int(m.group(1))
    elif "balcony" in t:
        counts.setdefault("balcony", 1)
    m = re.search(r"(\d)\s*kitchens?", t)
    if m:
        counts["kitchen"] = int(m.group(1))
    elif "kitchen" in t:
        counts.setdefault("kitchen", 1)
    if "living" in t or "hall" in t:
        counts.setdefault("living_room", 1)
    if "dining" in t:
        # dining often combined, but count separately if explicit number
        m2 = re.search(r"dining.*?(\d)", t)
        counts.setdefault("dining_room", 1)
    return counts

def extract_kitchen_type(text: str) -> str:
    t = text.lower()
    if "open kitchen" in t:
        return "open"
    if "closed kitchen" in t or "separate kitchen" in t:
        return "closed"
    return "open"

def extract_style(text: str) -> str:
    t = text.lower()
    for s in STYLE_KEYWORDS:
        if s in t:
            if s == "minimalist":
                return "minimal"
            return s
    return "modern"

def extract_direction(text: str) -> str:
    t = text.lower()
    for k, v in DIRECTION_MAP.items():
        if k in t:
            return v
    m = re.search(r"(east|west|north|south)\s*[\- ]?facing", t)
    if m:
        return m.group(1).lower()
    return "east"

def extract_floors(text: str) -> int:
    t = text.lower()
    m = re.search(r"(\d)\s*(floor|storey|story)", t)
    if m:
        try:
            return int(m.group(1))
        except:
            pass
    if "duplex" in t:
        return 2
    return 1

def normalize_structured(parsed: Dict[str, Any]) -> Dict[str, Any]:
    # sensible defaults & validation
    bedroom = parsed.get("bedrooms", 2)
    bathroom = parsed.get("bathrooms", 2)
    if bedroom < 1:
        bedroom = 2
    if bedroom > 5:
        bedroom = 5
    if bathroom < 1:
        bathroom = 1
    if bathroom > bedroom + 1:
        bathroom = bedroom
    area = parsed.get("total_area_sqft", 0)
    if area == 0:
        # estimate from BHK: 450 + 300 per bedroom + 400 living/kitchen
        area = 600 + bedroom * 280 + bathroom * 35
        parsed["_area_inferred"] = True
    else:
        parsed["_area_inferred"] = False
        if area < 350:
            area = 350
        if area > 6000:
            area = 6000
    parsed["bedrooms"] = bedroom
    parsed["bathrooms"] = bathroom
    parsed["total_area_sqft"] = float(area)
    # ensure kitchen & living
    if parsed.get("kitchens", 0) == 0:
        parsed["kitchens"] = 1
    if parsed.get("living_rooms", 0) == 0:
        parsed["living_rooms"] = 1
    return parsed

def parse_requirements(text: str) -> Dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("Requirement text is empty")
    raw = text.strip()
    low = raw.lower()
    # use spacy for entity hints if available
    doc = None
    try:
        nlp = get_nlp()
        if nlp is not None:
            doc = nlp(raw)
    except Exception:
        doc = None

    bhk = extract_bhk(low)
    area = extract_area(low)
    counts = extract_counts(low)
    kitchen_type = extract_kitchen_type(low)
    style = extract_style(low)
    direction = extract_direction(low)
    floors = extract_floors(low)

    bedrooms = counts.get("bedroom", bhk if bhk else 2)
    bathrooms = counts.get("bathroom", 2 if bedrooms >= 2 else 1)
    kitchens = counts.get("kitchen", 1)
    balconies = counts.get("balcony", 1 if "balcony" in low else 0)
    living = counts.get("living_room", 1)
    dining = counts.get("dining_room", 0)
    # explicit flags
    wants_furniture = "furniture" in low
    wants_lighting = "light" in low
    wants_plumbing = "plumb" in low or "bath" in low or "kitchen" in low

    parsed: Dict[str, Any] = {
        "original_text": raw,
        "bedrooms": int(bedrooms),
        "bathrooms": int(bathrooms),
        "kitchens": int(kitchens),
        "balconies": int(balconies),
        "living_rooms": int(living),
        "dining_rooms": int(dining),
        "total_area_sqft": float(area) if area else 0,
        "kitchen_type": kitchen_type,
        "style": style,
        "floors": int(floors),
        "main_entrance_direction": direction,
        "wants_furniture": wants_furniture,
        "wants_lighting": wants_lighting,
        "wants_plumbing": wants_plumbing,
        "explicit": {
            "bedrooms": bhk != 0 or "bedroom" in low or "bhk" in low,
            "bathrooms": "bath" in low,
            "area": area != 0,
            "direction": any(k in low for k in DIRECTION_MAP.keys()),
            "balcony": "balcony" in low or "terrace" in low,
            "kitchen_type": "open kitchen" in low or "closed kitchen" in low
        }
    }

    if doc is not None:
        # enrich: look for cardinal numbers via entities
        # fallback already covered
        pass

    parsed = normalize_structured(parsed)

    # warnings for inferred
    warnings: List[str] = []
    if not parsed["explicit"]["area"]:
        warnings.append(f"Built-up area not specified; inferred {int(parsed['total_area_sqft'])} sqft from BHK and room counts")
    if not parsed["explicit"]["direction"]:
        warnings.append(f"Entrance direction not specified; defaulting to {parsed['main_entrance_direction']}")
    if not parsed["explicit"]["balcony"] and parsed["balconies"] == 0:
        warnings.append("Balcony not requested; layout will exclude balcony")
    parsed["warnings"] = warnings
    parsed["inferred_defaults"] = {
        "area": not parsed["explicit"]["area"],
        "direction": not parsed["explicit"]["direction"]
    }
    return parsed
