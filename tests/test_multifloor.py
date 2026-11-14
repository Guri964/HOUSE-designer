import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from backend.parser.nlp_parser import parse_requirements
from backend.generator.floorplan_generator import generate_floorplan
from backend.validation.compliance import run_compliance
from backend.models.inference import GCNInference
from backend.cost.estimator import estimate_cost

gcn = GCNInference()


def _rooms_overlap(rooms):
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            a, b = rooms[i], rooms[j]
            if not (a["x"] + a["width"] <= b["x"] + 0.1 or b["x"] + b["width"] <= a["x"] + 0.1 or
                    a["y"] + a["height"] <= b["y"] + 0.1 or b["y"] + b["height"] <= a["y"] + 0.1):
                return True
    return False


def test_parser_detects_floors():
    p1 = parse_requirements("500 square feet, 2 bedrooms, 2 attached bathrooms, 1 kitchen")
    assert p1["floors"] == 1
    p2 = parse_requirements("500 square feet, 2 bedrooms, 2 attached bathrooms, 1 kitchen, 2 floors")
    assert p2["floors"] == 2
    p3 = parse_requirements("500 square feet, 2 bedrooms, 2 attached bathrooms, 1 kitchen, 3 floors")
    assert p3["floors"] == 3
    assert p1["bedrooms"] == 2 and p1["bathrooms"] == 2 and p1["kitchens"] == 1


def test_single_floor_no_staircase():
    p = parse_requirements("500 square feet, 2 bedrooms, 2 attached bathrooms, 1 kitchen")
    layout = generate_floorplan(p)
    assert layout["floors"] == 1
    assert layout["staircase"] is None
    assert len(layout["floor_plans"]) == 1
    assert not any(r["type"] == "staircase" for r in layout["rooms"])
    assert not _rooms_overlap(layout["rooms"])


def test_two_floor_generation():
    p = parse_requirements("500 square feet, 2 bedrooms, 2 attached bathrooms, 1 kitchen, 2 floors")
    layout = generate_floorplan(p)
    assert layout["floors"] == 2
    assert [fp["label"] for fp in layout["floor_plans"]] == ["Ground Floor", "First Floor"]
    # common footprint + aligned staircase
    w0 = layout["floor_plans"][0]["width"]
    assert all(fp["width"] == w0 and fp["height"] == layout["height"] for fp in layout["floor_plans"])
    stairs = [[r for r in fp["rooms"] if r["type"] == "staircase"][0] for fp in layout["floor_plans"]]
    assert all(s["x"] == stairs[0]["x"] and s["y"] == stairs[0]["y"] for s in stairs)
    # no overlaps within any floor
    assert all(not _rooms_overlap(fp["rooms"]) for fp in layout["floor_plans"])
    # ground keeps common areas; bedrooms distributed upstairs
    ground_types = {r["type"] for r in layout["floor_plans"][0]["rooms"]}
    assert "living_room" in ground_types and "kitchen" in ground_types
    upper_types = {r["type"] for r in layout["floor_plans"][1]["rooms"]}
    assert "bedroom" in upper_types


def test_three_floor_generation():
    p = parse_requirements("500 square feet, 2 bedrooms, 2 attached bathrooms, 1 kitchen, 3 floors")
    layout = generate_floorplan(p)
    assert layout["floors"] == 3
    assert [fp["label"] for fp in layout["floor_plans"]] == ["Ground Floor", "First Floor", "Second Floor"]
    stairs = [[r for r in fp["rooms"] if r["type"] == "staircase"][0] for fp in layout["floor_plans"]]
    assert all(s["x"] == stairs[0]["x"] and s["y"] == stairs[0]["y"] for s in stairs)
    assert all(not _rooms_overlap(fp["rooms"]) for fp in layout["floor_plans"])
    # every floor keeps a purpose (no duplicated layouts)
    type_sets = [{r["type"] for r in fp["rooms"]} for fp in layout["floor_plans"]]
    assert len({frozenset(ts) for ts in type_sets}) > 1


def test_compliance_and_gcn_multi_floor():
    for nf in (2, 3):
        p = parse_requirements(f"500 square feet, 2 bedrooms, 2 attached bathrooms, 1 kitchen, {nf} floors")
        layout = generate_floorplan(p)
        g = gcn.predict(layout)
        assert "score" in g and 0 <= g["score"] <= 1
        c = run_compliance(layout, p, g)
        assert c["status"] in ("FULLY_COMPLIANT", "PARTIALLY_COMPLIANT", "NON_COMPLIANT")
        assert 0 <= c["score"] <= 1
        cost = estimate_cost(layout)
        assert cost["grand_total"] > 0


def test_duplex_alias():
    p = parse_requirements("1000 square feet, 2 bedrooms, 2 bathrooms, 1 kitchen, duplex")
    assert p["floors"] == 2


# ---------- API level ----------
def get_client():
    from backend.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_generate_api_two_floors():
    c = get_client()
    r = c.post("/api/generate", json={"text": "500 square feet, 2 bedrooms, 2 attached bathrooms, 1 kitchen, 2 floors"})
    assert r.status_code == 200, r.get_data(as_text=True)
    j = r.json
    assert j["layout"]["floors"] == 2
    assert len(j["layout"]["floor_plans"]) == 2
    assert j["compliance"]["status"] in ("FULLY_COMPLIANT", "PARTIALLY_COMPLIANT", "NON_COMPLIANT")
    assert j["cost"]["grand_total"] > 0


def test_generate_api_three_floors():
    c = get_client()
    r = c.post("/api/generate", json={"text": "500 square feet, 2 bedrooms, 2 attached bathrooms, 1 kitchen, 3 floors"})
    assert r.status_code == 200, r.get_data(as_text=True)
    j = r.json
    assert j["layout"]["floors"] == 3
    assert len(j["layout"]["floor_plans"]) == 3


def test_validate_api_multi_floor():
    c = get_client()
    gen = c.post("/api/generate", json={"text": "500 square feet, 2 bedrooms, 2 attached bathrooms, 1 kitchen, 2 floors"}).json
    r = c.post("/api/validate", json={"layout": gen["layout"], "parsed": gen["parsed"]})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert "compliance" in r.json
