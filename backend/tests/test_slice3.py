"""Reminder timer, monthly limit, opt-out, delete, and the demo clock."""
from datetime import datetime

import pytest

from app import clock
from app.models import Shop
from app.services.scheduler import weekly_slots

MONDAY = datetime(2026, 11, 16, 11, 0)  # reminders default to Sunday 10:00


@pytest.fixture
def shop(client):
    clock.set_now(MONDAY)
    client.put("/api/settings", json={"upi_id": "sharmastore@okaxis", "name": "Sharma Store"})
    return client


def entry(client, phone="9876543210", bill="500", name="Ramesh"):
    return client.post("/api/entries", json={"phone": phone, "bill_amount": bill, "name": name}).json()["customer"]["id"]


def start_timer_and_approve(client):
    client.post("/api/settings/approve")
    client.post("/api/dev/run-scheduler")  # first run: the timer starts counting from now


def kinds(client, cid, kind="weekly_reminder"):
    return [m for m in client.get(f"/api/customers/{cid}").json()["messages"] if m["kind"] == kind]


# ---------- slots ----------
def test_weekly_slots():
    s = Shop(reminder_day=6, reminder_time="10:00")
    slots = weekly_slots(s, MONDAY, datetime(2026, 12, 6, 9, 0))  # just before the 3rd Sunday
    assert slots == [datetime(2026, 11, 22, 10), datetime(2026, 11, 29, 10)]
    # A slot exactly at "after" isn't repeated; one exactly at "upto" is included.
    assert weekly_slots(s, datetime(2026, 11, 22, 10), datetime(2026, 11, 29, 10)) == [datetime(2026, 11, 29, 10)]


# ---------- weekly reminders ----------
def test_no_reminders_until_approved(shop):
    cid = entry(shop)
    shop.post("/api/dev/run-scheduler")
    r = shop.post("/api/dev/advance", json={"days": 14}).json()
    assert r["reminders_sent"] == 0 and len(r["slots"]) == 2
    assert kinds(shop, cid) == []


def test_jump_three_weeks_sends_one_reminder_per_sunday(shop):
    cid = entry(shop, bill="640")
    start_timer_and_approve(shop)
    r = shop.post("/api/dev/advance", json={"days": 21}).json()
    assert r["reminders_sent"] == 3
    reminders = kinds(shop, cid)
    assert [m["created_at"] for m in reminders] == ["2026-12-06T10:00:00", "2026-11-29T10:00:00", "2026-11-22T10:00:00"]
    assert all(m["status"] == "sent_sim" for m in reminders)
    assert "Rs 640" in reminders[0]["body"] and "/pay/" in reminders[0]["body"] and "Reply STOP" in reminders[0]["body"]


def test_running_twice_never_repeats_a_slot(shop):
    cid = entry(shop)
    start_timer_and_approve(shop)
    shop.post("/api/dev/advance", json={"days": 7})
    shop.post("/api/dev/run-scheduler")
    shop.post("/api/dev/run-scheduler")
    assert len(kinds(shop, cid)) == 1


def test_customers_who_paid_or_owe_nothing_get_no_reminder(shop):
    cid = entry(shop, bill="300")
    start_timer_and_approve(shop)
    shop.post(f"/api/customers/{cid}/payments", json={"amount": "300"})
    shop.post("/api/dev/advance", json={"days": 7})
    assert kinds(shop, cid) == []


def test_bill_added_after_the_slot_waits_for_next_week(shop):
    start_timer_and_approve(shop)
    shop.post("/api/dev/advance", json={"days": 6, "hours": 23})  # Sunday 10:00 just passed
    cid = entry(shop)
    shop.post("/api/dev/advance", json={"days": 1})
    assert kinds(shop, cid) == []
    shop.post("/api/dev/advance", json={"days": 6})
    assert len(kinds(shop, cid)) == 1


def test_monthly_limit(shop):
    cid = entry(shop)
    shop.put("/api/settings", json={"max_reminders_per_month": 2})
    start_timer_and_approve(shop)
    r = shop.post("/api/dev/advance", json={"days": 35}).json()  # 5 Sundays
    assert r["reminders_sent"] == 2 and r["blocked_cap"] == 3
    statuses = [m["status"] for m in reversed(kinds(shop, cid))]
    assert statuses == ["sent_sim", "sent_sim", "blocked_cap", "blocked_cap", "blocked_cap"]
    # Sixth Sunday: the first reminder is now more than 30 days old, so one more is allowed.
    shop.post("/api/dev/advance", json={"days": 7})
    assert kinds(shop, cid)[0]["status"] == "sent_sim"


# ---------- quiet hours ----------
def test_night_message_delivered_in_the_morning(shop):
    clock.set_now(datetime(2026, 11, 16, 22, 30))
    cid = entry(shop)
    shop.post("/api/dev/run-scheduler")
    assert kinds(shop, cid, "bill_notice")[0]["status"] == "scheduled"
    shop.post("/api/dev/advance", json={"hours": 10})
    notice = kinds(shop, cid, "bill_notice")[0]
    assert notice["status"] == "sent_sim" and notice["sent_at"] == "2026-11-17T08:00:00"


def test_held_reminder_cancelled_if_they_pay_first(shop):
    shop.put("/api/settings", json={"reminder_time": "22:00"})  # inside quiet hours: held until 08:00
    cid = entry(shop)
    start_timer_and_approve(shop)
    shop.post("/api/dev/advance", json={"days": 6, "hours": 12})  # Sunday 23:00
    assert kinds(shop, cid)[0]["status"] == "scheduled"
    shop.post(f"/api/customers/{cid}/payments", json={"amount": "500"})
    r = shop.post("/api/dev/advance", json={"hours": 10}).json()
    assert r["cancelled_paid"] == 1
    assert kinds(shop, cid)[0]["status"] == "cancelled_paid"


# ---------- opt-out ----------
def phone_token(client, cid):
    return client.get(f"/api/customers/{cid}").json()["pay_link"].rsplit("/", 1)[1]


def test_stop_reply_opts_out_and_confirms(shop):
    cid = entry(shop)
    start_timer_and_approve(shop)
    chat = shop.post(f"/api/sim/phone/{phone_token(shop, cid)}/reply", json={"text": "STOP"}).json()
    assert [m["direction"] for m in chat["messages"][-2:]] == ["in", "out"]
    assert "won't get any more" in chat["messages"][-1]["body"]
    assert shop.get(f"/api/customers/{cid}").json()["opted_out"] is True
    shop.post("/api/dev/advance", json={"days": 14})
    assert kinds(shop, cid) == []


def test_start_reply_turns_messages_back_on(shop):
    cid = entry(shop)
    token = phone_token(shop, cid)
    shop.post(f"/api/sim/phone/{token}/reply", json={"text": "band karo"})
    shop.post(f"/api/sim/phone/{token}/reply", json={"text": "start"})
    assert shop.get(f"/api/customers/{cid}").json()["opted_out"] is False


def test_other_replies_are_just_stored(shop):
    cid = entry(shop)
    chat = shop.post(f"/api/sim/phone/{phone_token(shop, cid)}/reply", json={"text": "kal dunga"}).json()
    assert chat["messages"][-1]["body"] == "kal dunga" and chat["messages"][-1]["direction"] == "in"
    assert shop.get(f"/api/customers/{cid}").json()["opted_out"] is False


def test_shopkeeper_can_stop_and_resume(shop):
    cid = entry(shop)
    assert shop.post(f"/api/customers/{cid}/opt-out").json()["opted_out"] is True
    entry(shop, bill="100")  # bill notice to an opted-out customer is blocked
    assert kinds(shop, cid, "bill_notice")[0]["status"] == "blocked_opt_out"
    assert shop.post(f"/api/customers/{cid}/opt-in").json()["opted_out"] is False


# ---------- delete ----------
def test_delete_keeps_name_amounts_dates_and_erases_the_rest(shop):
    cid = shop.post("/api/entries", json={"phone": "9876543210", "bill_amount": "500", "name": "Ramesh", "items": [{"description": "Atta"}]}).json()["customer"]["id"]
    token = phone_token(shop, cid)
    shop.post("/api/sim/bank-notification", json={"payer_vpa": "ramesh@ybl", "payer_name": "RAMESH", "amount": "200", "note": f"dues C{cid}"})

    d = shop.delete(f"/api/customers/{cid}").json()
    assert d["deleted"] is True and d["name"] == "Ramesh"
    assert d["phone"].startswith("x") and d["pay_link"] is None
    assert d["messages"] == [] and d["dues"][0]["items"] == []
    assert d["dues"][0]["bill_paise"] == 50000 and d["balance_paise"] == 30000  # amounts kept
    assert d["payments"][0]["amount_paise"] == 20000
    assert shop.get(f"/api/pay/{token}").status_code == 404
    inc = shop.get("/api/incoming-payments").json()[0]
    assert inc["payer_vpa"] == "deleted" and inc["payer_name"] is None

    # Can't be messaged or re-enabled; the same phone number later is a new customer.
    assert shop.post(f"/api/customers/{cid}/opt-in").status_code == 422
    assert shop.delete(f"/api/customers/{cid}").status_code == 422
    assert entry(shop, name="Ramesh") != cid


# ---------- demo clock ----------
def test_clock_endpoints(shop):
    assert shop.get("/api/dev/clock").json()["now"] == "2026-11-16T11:00:00"
    shop.post("/api/dev/advance", json={"days": 1})
    assert shop.get("/api/dev/clock").json()["now"] == "2026-11-17T11:00:00"
    r = shop.post("/api/dev/reset-clock").json()
    assert r["offset_seconds"] == 0
