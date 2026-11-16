"""Call list (escalation) and call outcomes."""
from datetime import date, datetime, timedelta

import pytest

from app import clock

MONDAY = datetime(2026, 11, 16, 11, 0)  # reminders default to Sunday 10:00


@pytest.fixture
def shop(client):
    clock.set_now(MONDAY)
    client.put("/api/settings", json={"upi_id": "sharmastore@okaxis", "name": "Sharma Store"})
    client.post("/api/settings/approve")
    client.post("/api/dev/run-scheduler")  # start the timer from now
    return client


def entry(client, phone="9876543210", bill="500", name="Ramesh"):
    return client.post("/api/entries", json={"phone": phone, "bill_amount": bill, "name": name}).json()["customer"]["id"]


def advance(client, days=0, hours=0):
    return client.post("/api/dev/advance", json={"days": days, "hours": hours}).json()


def calls(client):
    return client.get("/api/call-list").json()


def ids(cards):
    return [c["customer_id"] for c in cards]


def detail(client, cid):
    return client.get(f"/api/customers/{cid}").json()


def reminders(client, cid, kind="weekly_reminder"):
    return [m for m in detail(client, cid)["messages"] if m["kind"] == kind and m["status"] == "sent_sim"]


def outcome(client, cid, **body):
    return client.post(f"/api/customers/{cid}/call-outcome", json=body)


# ---------- the call rule ----------
def test_after_30_days_reminders_stop_and_customer_is_on_call_list(shop):
    cid = entry(shop)
    advance(shop, days=29)
    assert ids(calls(shop)["to_call"]) == []
    assert detail(shop, cid)["collection_state"] == "reminders"
    advance(shop, days=1)
    card = calls(shop)["to_call"][0]
    assert card["customer_id"] == cid and card["oldest_age_days"] == 30
    assert card["reason"] == "Oldest bill is 30 days old"
    assert card["last_reminder_at"] == "2026-12-13T10:00:00"
    # Sundays 22, 29 Nov and 6, 13 Dec got reminders; none after the customer was escalated.
    advance(shop, days=14)
    assert len(reminders(shop, cid)) == 4


def test_big_balance_goes_to_call_list_sooner(shop):
    big = entry(shop, phone="9000000001", bill="2500", name="Big")
    small = entry(shop, phone="9000000002", bill="300", name="Small")
    advance(shop, days=13)
    assert ids(calls(shop)["to_call"]) == []
    advance(shop, days=1)
    cards = calls(shop)["to_call"]
    assert ids(cards) == [big]
    assert "Owes Rs 2,500" in cards[0]["reason"]
    assert detail(shop, small)["collection_state"] == "reminders"


def test_call_rule_uses_settings(shop):
    cid = entry(shop)
    shop.put("/api/settings", json={"escalation_days": 10})
    advance(shop, days=10)
    assert ids(calls(shop)["to_call"]) == [cid]


# ---------- promised a date ----------
def test_promise_takes_them_off_the_list_then_followup_then_broken(shop):
    cid = entry(shop)
    advance(shop, days=30)  # Wed 16 Dec
    r = outcome(shop, cid, outcome="promised_date", promised_date="2026-12-19", note="Salary on Saturday")
    assert r.status_code == 201
    lists = calls(shop)
    assert ids(lists["to_call"]) == [] and ids(lists["promised"]) == [cid]
    assert lists["promised"][0]["reason"] == "Promised to pay by Sat 19 Dec"

    advance(shop, days=3)  # Sat 19 Dec 11:00, the follow-up went at 10:00
    followups = reminders(shop, cid, "promise_followup")
    assert len(followups) == 1 and followups[0]["sent_at"] == "2026-12-19T10:00:00"
    assert "planned for today" in followups[0]["body"]
    assert ids(calls(shop)["promised"]) == [cid]  # still their day

    advance(shop, days=1)  # the day after, still unpaid
    card = calls(shop)["to_call"][0]
    assert card["customer_id"] == cid and "didn't pay" in card["reason"]
    assert detail(shop, cid)["promises"][0]["status"] == "broken"


def test_paying_in_full_keeps_the_promise_and_skips_followup(shop):
    cid = entry(shop)
    advance(shop, days=30)
    outcome(shop, cid, outcome="promised_date", promised_date="2026-12-19")
    shop.post(f"/api/customers/{cid}/payments", json={"amount": "500"})
    advance(shop, days=5)
    assert detail(shop, cid)["promises"][0]["status"] == "kept"
    assert reminders(shop, cid, "promise_followup") == []
    assert all(not v for v in calls(shop).values())


def test_promise_pauses_weekly_reminders_before_the_call_rule(shop):
    cid = entry(shop)
    # Promise made early (in slice 5 this will come from a reply like "kal dunga").
    outcome(shop, cid, outcome="promised_date", promised_date="2026-11-30")
    advance(shop, days=13)  # passes Sundays 22 and 29 Nov
    assert reminders(shop, cid) == []


def test_new_promise_replaces_old_one(shop):
    cid = entry(shop)
    advance(shop, days=30)
    outcome(shop, cid, outcome="promised_date", promised_date="2026-12-18")
    outcome(shop, cid, outcome="promised_date", promised_date="2026-12-20")
    statuses = [p["status"] for p in detail(shop, cid)["promises"]]
    assert statuses == ["pending", "replaced"]


@pytest.mark.parametrize("body,msg", [
    ({"outcome": "promised_date"}, "Pick the date"),
    ({"outcome": "promised_date", "promised_date": "2026-11-15"}, "past"),
    ({"outcome": "promised_date", "promised_date": "2027-03-01"}, "within 60 days"),
    ({"outcome": "maybe"}, "Unknown outcome"),
])
def test_outcome_validation(shop, body, msg):
    cid = entry(shop)
    r = outcome(shop, cid, **body)
    assert r.status_code == 422 and msg in r.text


def test_no_outcome_when_nothing_is_owed(shop):
    cid = entry(shop, bill="100")
    shop.post(f"/api/customers/{cid}/payments", json={"amount": "100"})
    assert outcome(shop, cid, outcome="disputed").status_code == 422


# ---------- disputed ----------
def test_dispute_stops_messages_until_resolved(shop):
    cid = entry(shop)
    advance(shop, days=30)
    outcome(shop, cid, outcome="disputed", note="Says the oil wasn't bought")
    lists = calls(shop)
    assert ids(lists["disputed"]) == [cid] and ids(lists["to_call"]) == []
    before = len(reminders(shop, cid))
    advance(shop, days=14)
    assert len(reminders(shop, cid)) == before

    r = shop.post(f"/api/customers/{cid}/resolve-dispute", json={"note": "Bill corrected"})
    assert r.status_code == 201
    assert ids(calls(shop)["to_call"]) == [cid]  # back under the normal rule (still old)
    assert shop.post(f"/api/customers/{cid}/resolve-dispute", json={}).status_code == 422


# ---------- written off ----------
def test_write_off_closes_dues_and_stops_everything(shop):
    cid = entry(shop, bill="700")
    advance(shop, days=30)
    assert outcome(shop, cid, outcome="written_off").json()["balance_paise"] == 70000
    d = detail(shop, cid)
    assert d["balance_paise"] == 0 and d["collection_state"] is None
    assert d["dues"][0]["status"] == "written_off" and d["dues"][0]["balance_paise"] == 70000
    assert all(not v for v in calls(shop).values())
    n = len(reminders(shop, cid))
    advance(shop, days=14)
    assert len(reminders(shop, cid)) == n
    assert [o["outcome"] for o in d["call_outcomes"]] == ["written_off"]
