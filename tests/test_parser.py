import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from backend.parser.nlp_parser import parse_requirements

def test_bhk_and_area():
    p = parse_requirements("2BHK 1200 sqft east facing")
    assert p["bedrooms"] == 2
    assert p["total_area_sqft"] == 1200
    assert p["main_entrance_direction"] == "east"

def test_north_facing():
    p = parse_requirements("3bhk 1500 sq feet north facing open kitchen")
    assert p["bedrooms"] == 3
    assert p["kitchen_type"] == "open"
    assert p["main_entrance_direction"] == "north"

def test_missing_area_inferred():
    p = parse_requirements("I want a 3BHK modern house with balcony")
    assert p["total_area_sqft"] > 0
    assert p["_area_inferred"] is True

def test_invalid_empty():
    try:
        parse_requirements("")
        assert False, "should raise"
    except ValueError:
        pass

def test_style_and_balcony():
    p = parse_requirements("luxury 4BHK 2200 sqft 2 balconies south facing")
    assert p["style"] == "luxury"
    assert p["balconies"] == 2
    assert p["main_entrance_direction"] == "south"

def test_area_normalization_small():
    p = parse_requirements("1BHK 100 sqft")
    # should clamp to min 350
    assert p["total_area_sqft"] >= 350
