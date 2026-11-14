from flask import Blueprint, request, jsonify
from typing import Dict, Any
import traceback

from ..parser.nlp_parser import parse_requirements
from ..generator.floorplan_generator import generate_floorplan
from ..models.inference import GCNInference
from ..validation.compliance import run_compliance
from ..cost.estimator import estimate_cost
from ..cost.rates import list_profiles
from ..schemas.layout_schema import validate_layout_dict
from ..config import COMPLIANCE_THRESHOLDS

api = Blueprint("api", __name__)
gcn = GCNInference()


def _compliance_status_rank(status: str) -> int:
    return {"FULLY_COMPLIANT": 2, "PARTIALLY_COMPLIANT": 1, "NON_COMPLIANT": 0}.get(status, 0)


def _run_multi_floor_compliance(layout: Dict[str, Any], parsed: Dict[str, Any], gcn_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run compliance per floor and aggregate. Each floor plan carries its own
    parsed subset (per-floor room program), so counts/areas are checked
    against what was actually placed on that floor."""
    floor_plans = layout.get("floor_plans") or []
    results = []
    for fp in floor_plans:
        fp_parsed = fp.get("parsed") or parsed
        fp_gcn = gcn.predict(fp)
        results.append(run_compliance(fp, fp_parsed, fp_gcn))
    if not results:
        return run_compliance(layout, parsed, gcn_result or {})

    score = round(sum(r["score"] for r in results) / len(results), 3)
    checks = [c for r in results for c in r.get("checks", [])]
    passed = [c for r in results for c in r.get("passed", [])]
    # For multi-floor, living room is only required on the ground floor.
    # Upper floors intentionally omit living rooms (bedrooms/bathrooms there),
    # so exclude 'living_present' failures from non-ground floors.
    failed = []
    for fi, r in enumerate(results):
        floor_idx = floor_plans[fi]["floor_index"]
        for f in r.get("failed", []):
            if f.get("id") == "living_present" and floor_idx != 0:
                continue
            failed.append(f)
    warnings = [c for r in results for c in r.get("warnings", [])]
    suggestions = [s for r in results for s in r.get("suggestions", [])]

    # Status follows the aggregate score with the same thresholds as run_compliance,
    # downgraded when any floor has hard failures.
    if score >= COMPLIANCE_THRESHOLDS["fully_compliant"]:
        status = "FULLY_COMPLIANT"
    elif score >= COMPLIANCE_THRESHOLDS["partially_compliant"]:
        status = "PARTIALLY_COMPLIANT"
    else:
        status = "NON_COMPLIANT"
    if any(r["failed"] for r in results) and status == "FULLY_COMPLIANT":
        status = "PARTIALLY_COMPLIANT"
    if any(c.get("id") == "no_overlap" and not c.get("passed") for c in checks):
        score = min(score, 0.55)
        status = "NON_COMPLIANT" if score < 0.60 else "PARTIALLY_COMPLIANT"

    return {
        "score": score,
        "status": status,
        "status_label": status.replace("_", " ").title(),
        "gcn_score": (gcn_result or {}).get("score"),
        "rule_score": round(sum(r.get("rule_score", 0) for r in results) / len(results), 3),
        "checks": checks,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "suggestions": suggestions,
        "type_counts": results[0].get("type_counts", {}),
        "multi_floor": True,
        "floor_results": [
            {"floor": fp["floor_index"], "label": fp["label"], "score": r["score"], "status": r["status"]}
            for fp, r in zip(floor_plans, results)
        ],
    }


@api.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "IntelliTwin API", "version": "1.0.0"})

@api.route("/model/status", methods=["GET"])
def model_status():
    return jsonify(gcn.status())

@api.route("/rates", methods=["GET"])
def rates():
    return jsonify({"profiles": list_profiles()})

@api.route("/parse", methods=["POST"])
def parse():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text") or data.get("requirement") or data.get("prompt") or ""
    if not text.strip():
        return jsonify({"error": "Requirement text is required"}), 400
    try:
        parsed = parse_requirements(text)
        return jsonify({"parsed": parsed})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Parsing failed", "detail": str(e)}), 500

@api.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text") or data.get("requirement") or data.get("prompt") or ""
    profile_id = data.get("rate_profile") or data.get("profile") or "india_tier2_2025"
    max_retries = int(data.get("max_retries", 3))
    # support direct structured parsed override
    parsed_override = data.get("parsed")
    if not text.strip() and not parsed_override:
        return jsonify({"error": "Requirement text is required"}), 400
    try:
        if parsed_override and isinstance(parsed_override, dict) and "bedrooms" in parsed_override:
            parsed = parsed_override
            # ensure minimal fields
            parsed.setdefault("kitchens", 1)
            parsed.setdefault("living_rooms", 1)
            parsed.setdefault("main_entrance_direction", "east")
            parsed.setdefault("style", "modern")
            parsed.setdefault("floors", 1)
            parsed.setdefault("total_area_sqft", 1200)
        else:
            parsed = parse_requirements(text)

        # generation with bounded retries: if compliance low, adjust? For now single + retry with same params
        best = None
        best_compliance = None
        best_gcn = None
        for attempt in range(max(1, max_retries)):
            layout = generate_floorplan(parsed)
            gcn_result = gcn.predict(layout)
            if int(layout.get("floors", 1)) > 1:
                compliance = _run_multi_floor_compliance(layout, parsed, gcn_result)
            else:
                compliance = run_compliance(layout, parsed, gcn_result)
            # select best by compliance score
            if best is None or compliance["score"] > best_compliance["score"]:
                best = layout
                best_compliance = compliance
                best_gcn = gcn_result
            if compliance["status"] == "FULLY_COMPLIANT":
                break
            # if non-compliant due to area mismatch, jitter not needed - retry will produce similar but we keep loop for future optimization

        cost = estimate_cost(best, profile_id)
        # room schedule
        room_schedule = [
            {"id": r["id"], "label": r["label"], "type": r["type"], "width": r["width"], "height": r["height"], "area": r["area"]}
            for r in best["rooms"]
        ]

        response = {
            "parsed": parsed,
            "layout": best,
            "gcn": best_gcn,
            "compliance": best_compliance,
            "cost": cost,
            "room_schedule": room_schedule,
            "summary": {
                "total_area": best["total_area"],
                "built_up_area": best["built_up_area"],
                "room_count": len(best["rooms"]),
                "orientation": best["orientation"],
                "style": parsed.get("style"),
            }
        }
        return jsonify(response)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Generation failed", "detail": str(e)}), 500

@api.route("/validate", methods=["POST"])
def validate():
    data = request.get_json(force=True, silent=True) or {}
    layout = data.get("layout")
    parsed = data.get("parsed")
    if not layout:
        return jsonify({"error": "layout is required"}), 400
    if not parsed:
        return jsonify({"error": "parsed requirements required for compliance"}), 400
    errs = validate_layout_dict(layout)
    if errs:
        return jsonify({"error": "Invalid layout", "details": errs}), 400
    try:
        gcn_result = gcn.predict(layout)
        if int(layout.get("floors", 1)) > 1:
            compliance = _run_multi_floor_compliance(layout, parsed, gcn_result)
        else:
            compliance = run_compliance(layout, parsed, gcn_result)
        return jsonify({"gcn": gcn_result, "compliance": compliance})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Validation failed", "detail": str(e)}), 500

@api.route("/cost", methods=["POST"])
def cost():
    data = request.get_json(force=True, silent=True) or {}
    layout = data.get("layout")
    profile_id = data.get("profile") or data.get("rate_profile") or "india_tier2_2025"
    if not layout:
        return jsonify({"error": "layout is required"}), 400
    try:
        result = estimate_cost(layout, profile_id)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Cost estimation failed", "detail": str(e)}), 500

@api.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404
