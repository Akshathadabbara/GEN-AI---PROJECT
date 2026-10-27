import pytest
from ai_matcher import HybridAIMatcher, build_item_representation, normalize_text
from llm_service import LLMExplanationService

def test_normalize_text():
    raw = "Dark Blue, Milton Bottle!! With Cap."
    normalized = normalize_text(raw)
    assert "dark blue milton bottle with cap" in normalized

def test_item_representation_privacy():
    item = {
        "item_name": "Calculator",
        "category": "Electronics",
        "description": "Casio FX-991EX scientific calculator",
        "student_name": "Confidential Student",
        "contact_number": "+919999999999",
        "registration_number": "REG12345"
    }
    rep = build_item_representation(item)
    assert "calculator" in rep.lower()
    assert "casio" in rep.lower()
    # Personal info must not be present in AI representations
    assert "Confidential Student" not in rep
    assert "+919999999999" not in rep
    assert "REG12345" not in rep

def test_semantic_similarity_ranking_water_bottle():
    matcher = HybridAIMatcher()
    lost_bottle = {
        "item_name": "Water bottle",
        "category": "Bottles & Flasks",
        "description": "Dark blue Milton bottle with a black cap",
        "location": "College library",
        "color": "Dark Blue",
        "brand": "Milton"
    }
    found_flask = {
        "item_name": "Flask",
        "category": "Bottles & Flasks",
        "description": "Navy blue Milton water bottle discovered near the library",
        "location": "Library entrance",
        "color": "Navy Blue",
        "brand": "Milton"
    }
    unrelated_keys = {
        "item_name": "Bike Keys",
        "category": "Keys",
        "description": "Set of Honda motorcycle keys on a leather ring",
        "location": "Main gate parking",
        "color": "Silver",
        "brand": "Honda"
    }

    res_matching = matcher.score_pair(lost_bottle, found_flask)
    res_unrelated = matcher.score_pair(lost_bottle, unrelated_keys)

    assert res_matching["similarity_score"] > res_unrelated["similarity_score"]
    assert res_matching["similarity_score"] >= 0.50
    assert "Strong potential match" in res_matching["confidence"] or "Possible match" in res_matching["confidence"]
    assert len(res_matching["evidence"]) > 0

def test_semantic_similarity_earbuds_vs_headphones():
    matcher = HybridAIMatcher()
    lost_earbuds = {
        "item_name": "Wireless earbuds",
        "category": "Electronics",
        "description": "Black wireless earbuds in a charging case near cafeteria",
        "location": "Cafeteria"
    }
    found_case = {
        "item_name": "Bluetooth earbud case",
        "category": "Electronics",
        "description": "A black Bluetooth earbud case discovered outside the canteen",
        "location": "Canteen"
    }
    res = matcher.score_pair(lost_earbuds, found_case)
    assert res["similarity_score"] >= 0.40
    assert res["confidence"] in ["Strong potential match", "Possible match"]

def test_deterministic_llm_explanation_fallback():
    service = LLMExplanationService()
    # When no API key is provided, it must fall back to grounded deterministic explanation
    service.api_key = ""
    lost = {"item_name": "Water Bottle", "location": "Library"}
    found = {"item_name": "Flask", "location": "Library entrance"}
    score_data = {"similarity_score": 0.78, "confidence": "Strong potential match", "evidence": ["Location proximity: Library"]}

    exp = service.generate_explanation(lost, found, score_data)
    assert "Water Bottle" in exp
    assert "Flask" in exp
    assert "78%" in exp
    assert len(exp) > 20
