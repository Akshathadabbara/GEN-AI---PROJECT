import pytest
import config
import os

TEST_DB = "test_privacy.db"

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "DATABASE", TEST_DB)
    import database
    monkeypatch.setattr(database, "DATABASE", TEST_DB)
    import app

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

def test_public_item_listing_redacts_private_contacts(client):
    client.post('/api/items', json={
        "type": "lost",
        "item_name": "Silver Laptop",
        "category": "Electronics",
        "description": "MacBook Air M2",
        "location": "Lab 3",
        "student_name": "Private Student",
        "registration_number": "PRIV_2023_99",
        "contact_number": "+91-9988776655",
        "contact_email": "private.student@campus.edu",
        "department": "CSE",
        "year_of_study": "4th Year"
    })

    # Query public feed
    res = client.get('/api/items')
    assert res.status_code == 200
    items = res.get_json()
    assert len(items) == 1
    item = items[0]

    # Contact numbers and student registration numbers must NOT be leaked
    assert item["contact_number"] != "+91-9988776655"
    assert item["contact_email"] != "private.student@campus.edu"
    assert item["registration_number"] != "PRIV_2023_99"
    assert "Verification Required" in item["contact_number"] or "Protected" in item["contact_number"]

def test_dashboard_stats_accurate(client):
    client.post('/api/items', json={
        "type": "lost",
        "item_name": "Black Backpack",
        "student_name": "John Doe",
        "registration_number": "REG1",
        "contact_number": "123",
        "contact_email": "jd@col.edu"
    })
    client.post('/api/items', json={
        "type": "found",
        "item_name": "Blue Bottle",
        "student_name": "Jane Doe",
        "registration_number": "REG2",
        "contact_number": "456",
        "contact_email": "jane@col.edu"
    })

    res = client.get('/api/dashboard/stats')
    assert res.status_code == 200
    stats = res.get_json()
    assert stats["total_lost"] == 1
    assert stats["total_found"] == 1
    assert stats["active_reports"] == 2
