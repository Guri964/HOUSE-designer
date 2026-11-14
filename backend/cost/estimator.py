from typing import Dict, List, Any
from .rates import get_rate_profile

def estimate_cost(layout: Dict[str, Any], profile_id: str = "india_tier2_2025") -> Dict[str, Any]:
    profile = get_rate_profile(profile_id)
    rates = profile["rates"]
    currency = profile["currency"]
    rooms = layout.get("rooms", [])
    total_area = float(layout.get("built_up_area", sum(r.get("area", 0) for r in rooms)))
    # counts
    type_counts = {}
    for r in rooms:
        type_counts[r["type"]] = type_counts.get(r["type"], 0) + 1
    bathrooms = type_counts.get("bathroom", 0)
    bedrooms = type_counts.get("bedroom", 0)
    balconies = type_counts.get("balcony", 0)
    kitchen = type_counts.get("kitchen", 0)
    living = type_counts.get("living_room", 0)

    lighting_count = len(layout.get("lighting", []))
    # fees
    items: List[Dict[str, Any]] = []

    def add_item(category, label, qty, unit, rate, subtotal):
        items.append({
            "category": category,
            "label": label,
            "quantity": round(qty, 2),
            "unit": unit,
            "rate": rate,
            "subtotal": round(subtotal, 2)
        })

    civil = total_area * rates["civil_per_sqft"]
    add_item("Civil", "Civil Construction (structure, walls, roof, foundation)", total_area, "sqft", rates["civil_per_sqft"], civil)

    flooring = total_area * rates["flooring_per_sqft"]
    add_item("Civil", "Flooring & Tiling", total_area, "sqft", rates["flooring_per_sqft"], flooring)

    painting = total_area * rates["painting_per_sqft"]
    add_item("Finishes", "Wall Finishes & Painting", total_area, "sqft", rates["painting_per_sqft"], painting)

    doors_windows = total_area * rates["doors_windows_per_sqft"]
    add_item("Finishes", "Doors & Windows", total_area, "sqft", rates["doors_windows_per_sqft"], doors_windows)

    electrical = total_area * rates["electrical_per_sqft"]
    add_item("Services", "Electrical Installations (wiring, switches, DB)", total_area, "sqft", rates["electrical_per_sqft"], electrical)

    lighting_amt = lighting_count * rates["lighting_per_fixture"]
    add_item("Services", f"Lighting Fixtures ({lighting_count} pts)", lighting_count, "fixture", rates["lighting_per_fixture"], lighting_amt)

    plumbing_amt = total_area * rates["plumbing_per_sqft"]
    add_item("Services", "Plumbing Lines (supply & drainage)", total_area, "sqft", rates["plumbing_per_sqft"], plumbing_amt)

    sanitary = bathrooms * rates["sanitary_per_bathroom"]
    add_item("Services", f"Sanitary Fixtures ({bathrooms} bathrooms)", bathrooms, "bathroom", rates["sanitary_per_bathroom"], sanitary)

    kitchen_amt = kitchen * rates["kitchen_per_unit"]
    add_item("Furniture & Kitchen", f"Kitchen Components ({kitchen} unit)", kitchen, "unit", rates["kitchen_per_unit"], kitchen_amt)

    furniture_bed = bedrooms * rates["furniture_per_bedroom"]
    add_item("Furniture & Kitchen", f"Bedroom Furniture ({bedrooms} bedrooms)", bedrooms, "bedroom", rates["furniture_per_bedroom"], furniture_bed)

    furniture_living = living * rates["furniture_living"]
    add_item("Furniture & Kitchen", f"Living Room Furniture", living, "unit", rates["furniture_living"], furniture_living)

    balcony_amt = balconies * rates["balcony_per_unit"]
    add_item("Furniture & Kitchen", f"Balcony Treatment ({balconies} units)", balconies, "unit", rates["balcony_per_unit"], balcony_amt)

    subtotal = sum(i["subtotal"] for i in items)
    contingency = subtotal * rates["contingency_pct"]
    add_item("Other", f"Contingency ({rates['contingency_pct']*100:.0f}%)", 1, "lump", round(contingency, 2), contingency)

    grand_total = subtotal + contingency

    # category totals
    cat_totals: Dict[str, float] = {}
    for it in items:
        cat_totals[it["category"]] = cat_totals.get(it["category"], 0) + it["subtotal"]

    by_category = [{"category": k, "total": round(v, 2), "pct": round(v / grand_total * 100, 1) if grand_total else 0} for k, v in cat_totals.items()]

    assumptions = [
        f"Profile: {profile['label']}",
        f"Built-up area basis: {total_area:.0f} sqft",
        f"Rates are approximate 2025 estimates; verify locally before procurement.",
        f"Civil rate per sqft includes structure, brickwork, plaster, roof slab; excludes land cost and approvals.",
        f"Electrical and plumbing are per sqft approximations; final depends on specifications and fixtures.",
        f"Furniture kitchen estimates are modular mid-range; luxury finishes will increase 25-60%.",
        f"Contingency covers wastage and minor variations; not a contractor margin.",
        f"Bathroom counts and fixture types affect sanitary estimate; plumbing routes influence line costs.",
        "Estimate excludes GST, architect fees, interior designer fees, and site-specific foundations where applicable."
    ]
    exclusions = [
        "Land cost, registration, and statutory approvals",
        "Boundary wall, gate, and external development beyond plinth",
        "Lift, STP, and specialized systems if any",
        "Premium finishes beyond selected rate profile",
        "Ongoing maintenance and utilities"
    ]

    return {
        "profile_id": profile_id,
        "profile_label": profile["label"],
        "currency": currency,
        "built_up_area": round(total_area, 2),
        "items": items,
        "subtotal": round(subtotal, 2),
        "contingency": round(contingency, 2),
        "grand_total": round(grand_total, 2),
        "cost_per_sqft": round(grand_total / total_area, 2) if total_area else 0,
        "by_category": by_category,
        "assumptions": assumptions,
        "exclusions": exclusions,
        "type_counts": type_counts,
        "note": "Approximate planning estimate only — not a binding quotation. Confirm with a licensed contractor and updated local Schedule of Rates."
    }
