"""Send on WhatsApp: manual sending, same guardrails as automatic reminders."""
from datetime import datetime
from urllib.parse import unquote

import pytest

from app import clock

DAY = datetime(2026, 11, 16, 11, 0)


@pytest.fixture
def shop(client):
    clock.set_now(DAY)
    client.put("/api/settings", json={"upi_id": "s@okaxis", "name": "Sharma Store"})
    return client


def new_customer(client, bill="500"):
    return client.post("/api/entries", json={"phone": "9876543210", "bill_amount": bill, "name": "Ramesh"}).json()["customer"]["id"]


def wa(client, cid):
    return client.post(f"/api/customers/{cid}/whatsapp").json()


def test_link_has_the_reminder_and_is_logged(shop):
    cid = new_customer(shop)
    r = wa(shop, cid)
    assert r["allowed"] and r["url"].startswith("https://wa.me/919876543210?text=")
    assert "Rs 500" in unquote(r["url"]) and "Reply STOP" in r["text"]
    kinds = [(m["kind"], m["status"]) for m in shop.get(f"/api/customers/{cid}").json()["messages"]]
    assert ("manual_reminder", "sent_manual") in kinds


def test_no_button_for_opted_out_or_paid(shop):
    cid = new_customer(shop)
    shop.post(f"/api/customers/{cid}/opt-out")
    assert wa(shop, cid) == {"allowed": False, "reason": "They opted out of messages", "text": None, "url": None}
    shop.post(f"/api/customers/{cid}/opt-in")
    shop.post(f"/api/customers/{cid}/payments", json={"amount": "500"})
    assert wa(shop, cid)["reason"] == "Nothing is pending"


def test_quiet_hours_block_manual_sending_too(shop):
    cid = new_customer(shop)
    clock.set_now(datetime(2026, 11, 16, 22, 30))
    r = wa(shop, cid)
    assert not r["allowed"] and r["reason"] == "Quiet hours: send after 08:00"


def test_manual_sends_count_towards_monthly_limit(shop):
    shop.put("/api/settings", json={"max_reminders_per_month": 2})
    cid = new_customer(shop)
    assert wa(shop, cid)["allowed"] and wa(shop, cid)["allowed"]
    r = wa(shop, cid)
    assert not r["allowed"] and "limit" in r["reason"]
