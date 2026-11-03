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


def test_admin_verify_endpoint(client):
    # Missing header
    res_no_key = client.post('/api/admin/verify')
    assert res_no_key.status_code == 403
    assert res_no_key.get_json()["authenticated"] is False

    # Invalid key
    res_wrong = client.post('/api/admin/verify', headers={"X-Admin-Key": "incorrect_secret"})
    assert res_wrong.status_code == 403
    assert res_wrong.get_json()["authenticated"] is False

    # Valid key
    res_correct = client.post('/api/admin/verify', headers={"X-Admin-Key": config.ADMIN_KEY})
    assert res_correct.status_code == 200
    assert res_correct.get_json()["authenticated"] is True


def test_unauthenticated_visitor_cannot_delete_item(client):
    # Create an item
    res = client.post('/api/items', json={
        "type": "lost",
        "item_name": "Leather Wallet",
        "student_name": "Student A",
        "registration_number": "REG01",
        "contact_number": "12345",
        "contact_email": "a@college.edu"
    })
    item_id = res.get_json()["id"]

    # Delete without admin key
    del_res = client.delete(f'/api/items/{item_id}')
    assert del_res.status_code == 403
    assert del_res.get_json()["success"] is False

    # Item must still exist
    get_res = client.get('/api/items')
    items = get_res.get_json()
    assert any(i["id"] == item_id for i in items)


def test_ordinary_student_with_invalid_key_cannot_delete_item(client):
    res = client.post('/api/items', json={
        "type": "found",
        "item_name": "Earphones",
        "student_name": "Student B",
        "registration_number": "REG02",
        "contact_number": "54321",
        "contact_email": "b@college.edu"
    })
    item_id = res.get_json()["id"]

    del_res = client.delete(f'/api/items/{item_id}', headers={"X-Admin-Key": "student_trying_to_guess"})
    assert del_res.status_code == 403
    assert del_res.get_json()["success"] is False


def test_authorized_admin_can_delete_item(client):
    res = client.post('/api/items', json={
        "type": "lost",
        "item_name": "Scientific Calculator",
        "student_name": "Student C",
        "registration_number": "REG03",
        "contact_number": "99999",
        "contact_email": "c@college.edu"
    })
    item_id = res.get_json()["id"]

    # Delete as authorized admin
    del_res = client.delete(f'/api/items/{item_id}', headers={"X-Admin-Key": config.ADMIN_KEY})
    assert del_res.status_code == 200
    data = del_res.get_json()
    assert data["success"] is True
    assert "deleted successfully" in data["message"]

    # Item must no longer be in the database
    get_res = client.get('/api/items')
    items = get_res.get_json()
    assert not any(i["id"] == item_id for i in items)


def test_delete_nonexistent_item_returns_404(client):
    del_res = client.delete('/api/items/999999', headers={"X-Admin-Key": config.ADMIN_KEY})
    assert del_res.status_code == 404
    assert del_res.get_json()["success"] is False


def test_delete_invalid_item_id(client):
    del_zero = client.delete('/api/items/0', headers={"X-Admin-Key": config.ADMIN_KEY})
    assert del_zero.status_code == 400
    assert del_zero.get_json()["success"] is False


def test_deletion_preserves_unrelated_items(client):
    # Add Item 1 and Item 2
    res1 = client.post('/api/items', json={
        "type": "lost",
        "item_name": "Preserved Item",
        "student_name": "Student X",
        "registration_number": "REGX",
        "contact_number": "111",
        "contact_email": "x@col.edu"
    })
    item1_id = res1.get_json()["id"]

    res2 = client.post('/api/items', json={
        "type": "found",
        "item_name": "Target Deletion Item",
        "student_name": "Student Y",
        "registration_number": "REGY",
        "contact_number": "222",
        "contact_email": "y@col.edu"
    })
    item2_id = res2.get_json()["id"]

    # Delete only Item 2
    del_res = client.delete(f'/api/items/{item2_id}', headers={"X-Admin-Key": config.ADMIN_KEY})
    assert del_res.status_code == 200

    # Verify Item 1 is intact
    get_res = client.get('/api/items')
    items = get_res.get_json()
    remaining_ids = [i["id"] for i in items]
    assert item1_id in remaining_ids
    assert item2_id not in remaining_ids


def test_deletion_cascades_claims_and_matches(client):
    # 1. Create a lost and found pair that matches
    lost_res = client.post('/api/items', json={
        "type": "lost",
        "item_name": "Blue Milton Bottle",
        "category": "Bottles & Flasks",
        "student_name": "Alice",
        "registration_number": "R1",
        "contact_number": "111",
        "contact_email": "a@col.edu"
    })
    lost_id = lost_res.get_json()["id"]

    found_res = client.post('/api/items', json={
        "type": "found",
        "item_name": "Blue Milton Bottle",
        "category": "Bottles & Flasks",
        "student_name": "Bob",
        "registration_number": "R2",
        "contact_number": "222",
        "contact_email": "b@col.edu"
    })
    found_id = found_res.get_json()["id"]

    # Verify candidate match exists
    matches_before = client.get('/api/matches').get_json()
    assert len(matches_before) >= 1

    # 2. Add claim on lost item
    claim_res = client.post('/api/claims', json={
        "item_id": lost_id,
        "claimant_name": "Alice Claimant",
        "claimant_contact": "111",
        "claimant_email": "a@col.edu",
        "verification_details": "Scratch on bottom"
    })
    assert claim_res.status_code == 201

    # 3. Delete lost item as admin
    del_res = client.delete(f'/api/items/{lost_id}', headers={"X-Admin-Key": config.ADMIN_KEY})
    assert del_res.status_code == 200

    # 4. Verify matches involving lost item are removed
    matches_after = client.get('/api/matches').get_json()
    for m in matches_after:
        assert m["lost_id"] != lost_id

    # 5. Verify claims on lost item are removed
    claims_after = client.get('/api/claims', headers={"X-Admin-Key": config.ADMIN_KEY}).get_json()
    for c in claims_after:
        assert c["item_id"] != lost_id

