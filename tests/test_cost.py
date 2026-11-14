import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from backend.parser.nlp_parser import parse_requirements
from backend.generator.floorplan_generator import generate_floorplan
from backend.cost.estimator import estimate_cost

def test_cost_structure():
    p = parse_requirements("3BHK 1500 sqft")
    layout = generate_floorplan(p)
    cost = estimate_cost(layout, "india_tier2_2025")
    assert "grand_total" in cost and cost["grand_total"] > 0
    assert "items" in cost and len(cost["items"]) >= 8
    assert "by_category" in cost
    assert "assumptions" in cost
    assert cost["currency"] == "INR"

def test_cost_rates():
    p = parse_requirements("2BHK 1100 sqft")
    layout = generate_floorplan(p)
    c1 = estimate_cost(layout, "india_tier2_2025")
    c2 = estimate_cost(layout, "india_metro_2025")
    assert c2["grand_total"] > c1["grand_total"]

def test_cost_per_sqft():
    p = parse_requirements("3BHK 1500 sqft")
    layout = generate_floorplan(p)
    cost = estimate_cost(layout)
    assert cost["cost_per_sqft"] == round(cost["grand_total"]/cost["built_up_area"],2)

def test_cost_contingency():
    p = parse_requirements("3BHK 1500 sqft")
    layout = generate_floorplan(p)
    cost = estimate_cost(layout)
    subtotal = sum(i["subtotal"] for i in cost["items"] if i["category"]!="Other")
    contingency = cost["contingency"]
    assert abs((cost["grand_total"] - subtotal - contingency)) < 1e-2
