from app import clock
from app.services.money import format_rupees, to_paise
from app.services.phone import InvalidPhone, normalize_phone
from decimal import Decimal
import pytest


# ---------- small helpers ----------
def test_phone_normalization():
    for raw in ["9876543210", "+91 98765-43210", "098765 43210", "91 9876543210"]:
        assert normalize_phone(raw) == "9876543210"
    for bad in ["12345", "5876543210", "", "98765432101"]:
        with pytest.raises(InvalidPhone):
            normalize_phone(bad)


def test_money():
    assert to_paise(Decimal("120.50")) == 12050
    assert to_paise(Decimal("0.1")) + to_paise(Decimal("0.2")) == 30
    assert format_rupees(12050) == "120.50"
    assert format_rupees(250000) == "2,500"


# ---------- entry ----------
def test_entry_creates_customer_and_due(client):
    r = client.post("/api/entries", json={"phone": "+91 98765 43210", "bill_amount": "500", "amount_paid": "120.50", "name": "Ramesh"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["is_new_customer"] is True
    assert body["customer"]["phone"] == "9876543210"
    assert body["due"]["balance_paise"] == 37950
    assert body["customer"]["balance_paise"] == 37950


def test_second_entry_reuses_customer_and_adds_up(client):
    client.post("/api/entries", json={"phone": "9876543210", "bill_amount": "300"})
    clock.advance(days=2)
    r = client.post("/api/entries", json={"phone": "98765 43210", "bill_amount": "200", "amount_paid": "50"})
    body = r.json()
    assert body["is_new_customer"] is False
    assert body["customer"]["balance_paise"] == 45000
    assert body["customer"]["open_dues"] == 2


def test_entry_without_name_keeps_existing_name(client):
    client.post("/api/entries", json={"phone": "9876543210", "bill_amount": "100", "name": "Sita"})
    r = client.post("/api/entries", json={"phone": "9876543210", "bill_amount": "100"})
    assert r.json()["customer"]["name"] == "Sita"


@pytest.mark.parametrize("payload,msg", [
    ({"phone": "123", "bill_amount": "100"}, "10-digit"),
    ({"phone": "9876543210", "bill_amount": "100", "amount_paid": "100"}, "Nothing is owed"),
])
def test_entry_rejects_bad_input(client, payload, msg):
    r = client.post("/api/entries", json=payload)
    assert r.status_code == 422
    assert msg in r.text


def test_entry_rejects_zero_bill(client):
    assert client.post("/api/entries", json={"phone": "9876543210", "bill_amount": "0"}).status_code == 422


def test_optional_items_are_stored(client):
    r = client.post("/api/entries", json={
        "phone": "9876543210", "bill_amount": "180",
        "items": [{"description": "Atta", "qty": "5 kg", "amount": "150"}, {"description": "  "}],
    })
    items = r.json()["due"]["items"]
    assert items == [{"description": "Atta", "qty": "5 kg", "amount_paise": 15000}]


# ---------- customers ----------
def test_customer_list_sorted_by_balance_and_searchable(client):
    client.post("/api/entries", json={"phone": "9000000001", "bill_amount": "100", "name": "Asha"})
    client.post("/api/entries", json={"phone": "9000000002", "bill_amount": "900", "name": "Bharat"})
    names = [c["name"] for c in client.get("/api/customers").json()]
    assert names == ["Bharat", "Asha"]
    assert [c["name"] for c in client.get("/api/customers", params={"q": "ash"}).json()] == ["Asha"]
    assert [c["name"] for c in client.get("/api/customers", params={"q": "0002"}).json()] == ["Bharat"]


def test_customer_detail(client):
    cid = client.post("/api/entries", json={"phone": "9000000001", "bill_amount": "100"}).json()["customer"]["id"]
    d = client.get(f"/api/customers/{cid}").json()
    assert d["consent_method"] == "given_to_shopkeeper"
    assert len(d["dues"]) == 1
    assert client.get("/api/customers/999").status_code == 404


# ---------- settings ----------
def test_settings_default_unapproved_with_opt_out_in_preview(client):
    s = client.get("/api/settings").json()
    assert s["approved"] is False
    assert "Reply STOP" in s["preview"]


def test_approval_cleared_when_wording_changes(client):
    assert client.post("/api/settings/approve").json()["approved"] is True
    # Changing a non-wording setting keeps the approval...
    assert client.put("/api/settings", json={"escalation_days": 20}).json()["approved"] is True
    # ...changing the wording or schedule clears it.
    r = client.put("/api/settings", json={"message_template": "Hello {name}, Rs {amount} pending. Pay: {link}"})
    assert r.json()["approved"] is False
    client.post("/api/settings/approve")
    assert client.put("/api/settings", json={"reminder_time": "11:30"}).json()["approved"] is False


def test_template_must_have_amount_and_link(client):
    r = client.put("/api/settings", json={"message_template": "Please pay soon {name}"})
    assert r.status_code == 422 and "{amount}" in r.text
    r = client.put("/api/settings", json={"message_template": "Pay {amount} at {link} or {threat}"})
    assert r.status_code == 422 and "threat" in r.text


def test_settings_validation(client):
    assert client.put("/api/settings", json={"reminder_time": "25:00"}).status_code == 422
    assert client.put("/api/settings", json={"reminder_day": 7}).status_code == 422
    assert client.put("/api/settings", json={"escalation_amount": "1500"}).json()["escalation_amount_paise"] == 150000
