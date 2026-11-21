"""Pilot mode: shops log in, and each shop only ever sees its own data."""
from datetime import datetime

import pytest

from app import clock
from app.config import settings


@pytest.fixture
def pilot(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    clock.set_now(datetime(2026, 11, 16, 11, 0))
    return client


def signup(client, phone, name="Shop", pin="1234"):
    r = client.post("/api/auth/signup", json={"shop_name": name, "phone": phone, "pin": pin})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_login_required_in_pilot_mode(pilot):
    assert pilot.get("/api/customers").status_code == 401
    assert pilot.get("/api/auth/me").json() == {"auth_required": True, "logged_in": False}


def test_shops_never_see_each_others_data(pilot):
    a = signup(pilot, "9000000001", "Asha Store")
    b = signup(pilot, "9000000002", "Bharat Store")
    pilot.post("/api/entries", json={"phone": "9876543210", "bill_amount": "500", "name": "Ramesh"}, headers=a)
    pilot.post("/api/entries", json={"phone": "9876543210", "bill_amount": "300", "name": "Ramesh B"}, headers=b)
    ca = pilot.get("/api/customers", headers=a).json()
    cb = pilot.get("/api/customers", headers=b).json()
    assert [(c["name"], c["balance_paise"]) for c in ca] == [("Ramesh", 50000)]
    assert [(c["name"], c["balance_paise"]) for c in cb] == [("Ramesh B", 30000)]
    # Shop B can't open shop A's customer by id.
    assert pilot.get(f"/api/customers/{ca[0]['id']}", headers=b).status_code == 404
    assert pilot.get("/api/settings", headers=a).json()["name"] == "Asha Store"
    assert pilot.get("/api/auth/me", headers=b).json()["shop_name"] == "Bharat Store"


def test_login_logout_and_wrong_pin_lockout(pilot):
    signup(pilot, "9000000001", pin="4321")
    assert pilot.post("/api/auth/login", json={"phone": "9000000001", "pin": "1111"}).status_code == 401
    ok = pilot.post("/api/auth/login", json={"phone": "+91 90000 00001", "pin": "4321"})
    assert ok.status_code == 200
    h = {"Authorization": f"Bearer {ok.json()['token']}"}
    assert pilot.get("/api/customers", headers=h).status_code == 200
    pilot.post("/api/auth/logout", headers=h)
    assert pilot.get("/api/customers", headers=h).status_code == 401
    for _ in range(5):
        pilot.post("/api/auth/login", json={"phone": "9000000001", "pin": "0000"})
    r = pilot.post("/api/auth/login", json={"phone": "9000000001", "pin": "4321"})
    assert r.status_code == 401 and "15 minutes" in r.text  # locked even with the right PIN


def test_signup_validation(pilot):
    assert pilot.post("/api/auth/signup", json={"shop_name": "S", "phone": "9000000001", "pin": "12"}).status_code == 422
    signup(pilot, "9000000001")
    r = pilot.post("/api/auth/signup", json={"shop_name": "S", "phone": "9000000001", "pin": "1234"})
    assert r.status_code == 422 and "already has a shop" in r.text


def test_customer_pages_work_without_login_and_show_their_own_shop(pilot):
    a = signup(pilot, "9000000001", "Asha Store")
    pilot.put("/api/settings", json={"upi_id": "asha@okaxis"}, headers=a)
    cid = pilot.post("/api/entries", json={"phone": "9876543210", "bill_amount": "500"}, headers=a).json()["customer"]["id"]
    token = pilot.get(f"/api/customers/{cid}", headers=a).json()["pay_link"].rsplit("/", 1)[1]
    assert pilot.get(f"/api/pay/{token}").json()["shop_name"] == "Asha Store"  # no login
    assert pilot.get(f"/api/sim/phone/{token}").json()["shop_name"] == "Asha Store"
    # A payment to Asha's UPI ID is matched inside Asha's shop.
    r = pilot.post("/api/sim/bank-notification", json={"payer_vpa": "x@ybl", "payee_vpa": "asha@okaxis", "amount": "500",
                                                       "note": f"dues C{cid}"})
    assert r.json()["status"] == "matched_auto"
    assert pilot.get(f"/api/customers/{cid}", headers=a).json()["balance_paise"] == 0


def test_local_mode_needs_no_login(client):
    assert client.get("/api/customers").status_code == 200
    assert client.get("/api/auth/me").json()["auth_required"] is False
