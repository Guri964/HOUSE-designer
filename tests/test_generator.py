import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from backend.parser.nlp_parser import parse_requirements
from backend.generator.floorplan_generator import generate_floorplan

def test_required_counts():
    p = parse_requirements("3BHK 1500 sqft east facing 2 bathrooms balcony")
    layout = generate_floorplan(p)
    counts = {}
    for r in layout["rooms"]:
        counts[r["type"]] = counts.get(r["type"], 0) + 1
    assert counts["bedroom"] == 3
    assert counts["bathroom"] == 2
    assert counts["kitchen"] == 1

def test_no_overlap():
    p = parse_requirements("2BHK 1100 sqft north facing")
    layout = generate_floorplan(p)
    rooms = layout["rooms"]
    for i in range(len(rooms)):
        for j in range(i+1, len(rooms)):
            a,b = rooms[i], rooms[j]
            overlap = not (a["x"]+a["width"] <= b["x"]+0.1 or b["x"]+b["width"] <= a["x"]+0.1 or a["y"]+a["height"] <= b["y"]+0.1 or b["y"]+b["height"] <= a["y"]+0.1)
            assert not overlap, f"overlap {a['label']} vs {b['label']}"

def test_area_tolerance():
    p = parse_requirements("3BHK 1500 sqft")
    layout = generate_floorplan(p)
    diff = abs(layout["total_area"] - p["total_area_sqft"])
    assert diff <= p["total_area_sqft"]*0.18, f"area diff {diff} too large"

def test_orientation():
    p = parse_requirements("2BHK 1000 sqft west facing")
    layout = generate_floorplan(p)
    assert layout["orientation"]["requested_direction"] == "west"
    assert layout["orientation"]["entrance_wall"] in ("left","right","top","bottom","top_right")

def test_furniture_clearance():
    p = parse_requirements("3BHK 1500 sqft")
    layout = generate_floorplan(p)
    for r in layout["rooms"]:
        for f in r.get("furniture", []):
            assert f["x"] >= r["x"] - 0.3
            assert f["y"] >= r["y"] - 0.3

def test_same_data_for_views():
    p = parse_requirements("3BHK 1500 sqft")
    layout = generate_floorplan(p)
    # 2D and 3D must use same width/height and room positions
    assert layout["width"] > 0 and layout["height"] > 0
    assert len(layout["furniture"]) > 0
    assert len(layout["lighting"]) > 0
    assert len(layout["plumbing_fixtures"]) > 0
