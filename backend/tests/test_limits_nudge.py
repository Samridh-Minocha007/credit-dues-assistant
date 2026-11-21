"""Credit limit warning, part-payment nudge and payday reminder."""
from datetime import datetime

import pytest

from app import clock
from app.services.scheduler import nudge_amount, payday_slots
from app.models import Shop

MONDAY = datetime(2026, 11, 16, 11, 0)


@pytest.fixture
def shop(client):
    clock.set_now(MONDAY)
    client.put("/api/settings", json={"upi_id": "s@okaxis"})
    client.post("/api/settings/approve")
    client.post("/api/dev/run-scheduler")
    return client


def entry(client, bill, phone="9876543210"):
    return client.post("/api/entries", json={"phone": phone, "bill_amount": bill}).json()


def test_shop_default_limit_and_customer_override(shop):
    shop.put("/api/settings", json={"default_credit_limit": "1000"})
    e = entry(shop, "800")
    assert e["over_limit"] is False and e["customer"]["credit_limit_paise"] == 100000
    assert entry(shop, "300")["over_limit"] is True  # 1,100 > 1,000
    cid = e["customer"]["id"]
    d = shop.patch(f"/api/customers/{cid}", json={"credit_limit": "5000"}).json()
    assert d["credit_limit_paise"] == 500000 and d["own_credit_limit_paise"] == 500000
    assert entry(shop, "100")["over_limit"] is False
    d = shop.patch(f"/api/customers/{cid}", json={"credit_limit": "0"}).json()  # back to shop default
    assert d["own_credit_limit_paise"] is None and d["credit_limit_paise"] == 100000


def test_no_limit_by_default(shop):
    e = entry(shop, "50000")
    assert e["over_limit"] is False and e["customer"]["credit_limit_paise"] is None


def test_rename_customer(shop):
    cid = entry(shop, "100")["customer"]["id"]
    assert shop.patch(f"/api/customers/{cid}", json={"name": "  Ramesh K "}).json()["name"] == "Ramesh K"


def test_nudge_amount():
    assert nudge_amount(15000) is None  # under Rs 200: no nudge
    assert nudge_amount(84000) == 40000  # Rs 840 -> Rs 400
    assert nudge_amount(20000) == 10000


def test_nudge_added_to_reminder_only_when_switched_on(shop):
    cid = entry(shop, "840")["customer"]["id"]
    shop.post("/api/dev/advance", json={"days": 7})
    first = [m for m in shop.get(f"/api/customers/{cid}").json()["messages"] if m["kind"] == "weekly_reminder"][0]
    assert "Even Rs" not in first["body"]
    shop.put("/api/settings", json={"part_payment_nudge": True})
    shop.post("/api/dev/advance", json={"days": 7})
    latest = [m for m in shop.get(f"/api/customers/{cid}").json()["messages"] if m["kind"] == "weekly_reminder"][0]
    assert "Even Rs 400 today would help." in latest["body"] and latest["body"].endswith("Reply STOP to stop these messages.")


def test_payday_slots():
    s = Shop(reminder_time="10:00")
    assert payday_slots(s, datetime(2026, 11, 16), datetime(2027, 1, 15)) == [datetime(2026, 12, 1, 10), datetime(2027, 1, 1, 10)]


def test_payday_reminder_on_the_first(shop):
    cid = entry(shop, "500")["customer"]["id"]
    shop.put("/api/settings", json={"payday_reminder": True, "escalation_days": 90})
    r = shop.post("/api/dev/advance", json={"days": 16}).json()  # to 2 Dec, passing 22 Nov, 29 Nov, 1 Dec
    kinds = [m["kind"] for m in shop.get(f"/api/customers/{cid}").json()["messages"] if m["status"] == "sent_sim"]
    assert kinds.count("payday_reminder") == 1 and kinds.count("weekly_reminder") == 2
    assert r["reminders_sent"] == 3
