import pytest
import json
import sqlite3
import os
import config

# Use a test database to avoid interfering with existing items
TEST_DB = "test_lost_found.db"

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "DATABASE", TEST_DB)
    import database
    monkeypatch.setattr(database, "DATABASE", TEST_DB)
    import app
    
    # Initialize fresh test database schema
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass

    database.init_db()

    app.app.config['TESTING'] = True
    with app.app.test_client() as client:
        yield client

    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass

def test_app_starts_and_serves_index(client):
    res = client.get('/')
    assert res.status_code == 200

def test_get_items_empty_initially(client):
    res = client.get('/api/items')
    assert res.status_code == 200
    assert res.get_json() == []

def test_report_item_validation(client):
    # Missing required fields
    res = client.post('/api/items', json={
        "type": "lost"
    })
    assert res.status_code == 400
    assert "Missing required fields" in res.get_json()["message"]

def test_report_lost_and_found_triggers_match(client):
    # 1. Report a lost item
    lost_data = {
        "type": "lost",
        "item_name": "Milton Water Bottle",
        "category": "Bottles & Flasks",
        "description": "Dark blue insulated water bottle with black cap",
        "location": "Library",
        "color": "Dark Blue",
        "brand": "Milton",
        "student_name": "Alice Smith",
        "registration_number": "2023CS101",
        "contact_number": "+919123456789",
        "contact_email": "alice@college.edu",
        "department": "Computer Science",
        "year_of_study": "2nd Year"
    }
    res_lost = client.post('/api/items', json=lost_data)
    assert res_lost.status_code == 201
    lost_id = res_lost.get_json()["id"]

    # 2. Report a found item that matches
    found_data = {
        "type": "found",
        "item_name": "Blue Flask",
        "category": "Bottles & Flasks",
        "description": "Navy blue Milton flask found near library entrance",
        "location": "Library entrance",
        "color": "Navy Blue",
        "brand": "Milton",
        "student_name": "Bob Jones",
        "registration_number": "2023EC202",
        "contact_number": "+919876543210",
        "contact_email": "bob@college.edu",
        "department": "Electronics",
        "year_of_study": "3rd Year"
    }
    res_found = client.post('/api/items', json=found_data)
    assert res_found.status_code == 201
    found_id = res_found.get_json()["id"]

    # Candidate matches should have been created
    matches_res = client.get('/api/matches')
    assert matches_res.status_code == 200
    matches = matches_res.get_json()
    assert len(matches) == 1
    m = matches[0]
    assert m["lost_id"] == lost_id
    assert m["found_id"] == found_id
    assert m["similarity_score"] >= 0.50
    assert "explanation" in m
    assert m["explanation"] != ""

def test_lost_does_not_match_other_lost(client):
    # Add two lost items
    client.post('/api/items', json={
        "type": "lost",
        "item_name": "Black Umbrella",
        "student_name": "Student A",
        "registration_number": "REG1",
        "contact_number": "11111",
        "contact_email": "a@college.edu"
    })
    client.post('/api/items', json={
        "type": "lost",
        "item_name": "Black Umbrella",
        "student_name": "Student B",
        "registration_number": "REG2",
        "contact_number": "22222",
        "contact_email": "b@college.edu"
    })

    matches_res = client.get('/api/matches')
    assert matches_res.status_code == 200
    matches = matches_res.get_json()
    # Lost items must never be paired with lost items
    assert len(matches) == 0

def test_resolved_item_excluded_from_active_matches(client):
    # Create lost and found pair
    client.post('/api/items', json={
        "type": "lost",
        "item_name": "iPhone 13",
        "category": "Electronics",
        "student_name": "Alice",
        "registration_number": "REG1",
        "contact_number": "111",
        "contact_email": "alice@col.edu"
    })
    res_f = client.post('/api/items', json={
        "type": "found",
        "item_name": "iPhone 13",
        "category": "Electronics",
        "student_name": "Bob",
        "registration_number": "REG2",
        "contact_number": "222",
        "contact_email": "bob@col.edu"
    })
    found_id = res_f.get_json()["id"]

    # Mark found item as resolved
    patch_res = client.patch(
        f'/api/items/{found_id}/status',
        headers={"X-Admin-Key": config.ADMIN_KEY},
        json={"status": "resolved"}
    )
    assert patch_res.status_code == 200

    # Matches should no longer show the resolved pair
    matches_res = client.get('/api/matches?status=pending')
    assert len(matches_res.get_json()) == 0

def test_claim_request_workflow(client):
    # Create an item
    res = client.post('/api/items', json={
        "type": "found",
        "item_name": "Casio Watch",
        "student_name": "Finder",
        "registration_number": "REG1",
        "contact_number": "111",
        "contact_email": "finder@col.edu"
    })
    item_id = res.get_json()["id"]

    # Submit a claim
    claim_res = client.post('/api/claims', json={
        "item_id": item_id,
        "claimant_name": "Owner",
        "claimant_contact": "+9199999999",
        "claimant_email": "owner@col.edu",
        "verification_details": "Back panel has scratch with serial ending in 42"
    })
    assert claim_res.status_code == 201

    # Unauthorized access to claims must be blocked
    get_claims_unauth = client.get('/api/claims')
    assert get_claims_unauth.status_code == 403

    # Authorized staff inspects claims
    get_claims_auth = client.get('/api/claims', headers={"X-Admin-Key": config.ADMIN_KEY})
    assert get_claims_auth.status_code == 200
    claims = get_claims_auth.get_json()
    assert len(claims) == 1
    assert claims[0]["claimant_name"] == "Owner"
