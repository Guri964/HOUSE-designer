import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from backend.parser.nlp_parser import parse_requirements
from backend.generator.floorplan_generator import generate_floorplan
from backend.validation.compliance import run_compliance
from backend.models.inference import GCNInference

def test_compliance_structure():
    p = parse_requirements("3BHK 1500 sqft east facing 2 bathrooms")
    layout = generate_floorplan(p)
    gcn = GCNInference().predict(layout)
    comp = run_compliance(layout, p, gcn)
    assert "score" in comp and 0 <= comp["score"] <= 1
    assert comp["status"] in ("FULLY_COMPLIANT","PARTIALLY_COMPLIANT","NON_COMPLIANT")
    assert "checks" in comp and len(comp["checks"]) > 10

def test_gcn_baseline():
    p = parse_requirements("2BHK 1100 sqft")
    layout = generate_floorplan(p)
    gcn = GCNInference().predict(layout)
    assert "score" in gcn and 0 <= gcn["score"] <= 1
    assert "source" in gcn

def test_hard_failure_overlap():
    p = parse_requirements("3BHK 1500 sqft")
    layout = generate_floorplan(p)
    # force overlap
    layout["rooms"][0]["x"] = layout["rooms"][1]["x"]
    layout["rooms"][0]["y"] = layout["rooms"][1]["y"]
    comp = run_compliance(layout, p, {"score":0.9})
    # should not be fully compliant
    assert comp["status"] != "FULLY_COMPLIANT"

def test_graph_build():
    from backend.validation.graph_builder import build_graph_features
    p = parse_requirements("2BHK 1000 sqft")
    layout = generate_floorplan(p)
    graph = build_graph_features(layout)
    assert graph["num_nodes"] == len(layout["rooms"])
    assert graph["num_features"] == 14
    assert len(graph["node_features"][0]) == 14

def test_inference_artifact_status():
    gcn = GCNInference()
    status = gcn.status()
    assert "model_exists" in status
    assert "inference_ready" in status
