"""Metrics: each number checked against a small, hand-worked example."""
from datetime import datetime

import pytest

from app import clock

MONDAY = datetime(2026, 11, 16, 11, 0)


@pytest.fixture
def shop(client):
    clock.set_now(MONDAY)
    client.put("/api/settings", json={"upi_id": "sharmastore@okaxis", "name": "Sharma Store"})
    client.post("/api/settings/approve")
    client.post("/api/dev/run-scheduler")
    return client


def entry(client, phone, bill, name=None):
    return client.post("/api/entries", json={"phone": phone, "bill_amount": bill, "name": name}).json()["customer"]["id"]


def pay(client, cid, amount):
    assert client.post(f"/api/customers/{cid}/payments", json={"amount": amount}).status_code == 200


def advance(client, days):
    client.post("/api/dev/advance", json={"days": days})


def metrics(client):
    return client.get("/api/metrics").json()


def test_empty_shop_has_no_rates(client):
    m = metrics(client)
    assert m["recovery"]["rate"] is None and m["recovery"]["mature_bills"] == 0
    assert m["guardrails"]["opt_out_rate"] is None


def test_recovered_within_30_days(shop):
    a = entry(shop, "9000000001", "100")  # paid on day 10  -> recovered
    b = entry(shop, "9000000002", "200")  # paid on day 40  -> late, not recovered
    entry(shop, "9000000003", "300")      # never paid      -> not recovered
    d = entry(shop, "9000000004", "400")  # written off     -> not recovered
    advance(shop, 10)
    pay(shop, a, "100")
    advance(shop, 30)
    pay(shop, b, "200")
    shop.post(f"/api/customers/{d}/call-outcome", json={"outcome": "written_off"})
    advance(shop, 5)                      # day 45
    entry(shop, "9000000005", "500")      # today: too new to judge

    r = metrics(shop)["recovery"]
    assert r["mature_bills"] == 4 and r["recovered_bills"] == 1 and r["rate"] == 0.25
    assert r["mature_paise"] == 100000 and r["recovered_paise"] == 10000 and r["rate_by_amount"] == 0.1
    assert r["written_off_bills"] == 1 and r["too_new_bills"] == 1


def test_paid_at_counter_part_is_not_counted_as_credit(shop):
    shop.post("/api/entries", json={"phone": "9000000001", "bill_amount": "500", "amount_paid": "200"})
    advance(shop, 31)
    assert metrics(shop)["recovery"]["mature_paise"] == 30000


def test_experiment_arms_use_the_switch_at_the_time_of_the_bill(shop):
    a = entry(shop, "9000000001", "100")  # baseline
    shop.put("/api/settings", json={"reply_parsing_enabled": True})
    b = entry(shop, "9000000002", "100")  # replies on
    entry(shop, "9000000003", "100")      # replies on, never paid
    shop.put("/api/settings", json={"reply_parsing_enabled": False})  # switching off later doesn't move old bills
    pay(shop, a, "100")
    pay(shop, b, "100")
    advance(shop, 31)
    on, off = metrics(shop)["experiment"]["arms"]
    assert on["label"] == "Reading replies: on" and on["mature_bills"] == 2 and on["rate"] == 0.5
    assert off["mature_bills"] == 1 and off["rate"] == 1.0
    assert on["small_sample"] and off["small_sample"]


def test_opt_out_rate_and_deleted_counted_separately(shop):
    a = entry(shop, "9000000001", "100")
    entry(shop, "9000000002", "100")
    c = entry(shop, "9000000003", "100")
    entry(shop, "9000000004", "100")
    shop.post(f"/api/customers/{a}/opt-out")
    shop.delete(f"/api/customers/{c}")
    g = metrics(shop)["guardrails"]
    assert g["messaged_customers"] == 3  # the deleted customer's messages are gone
    assert g["opted_out"] == 1 and g["opt_out_rate"] == pytest.approx(0.3333, abs=1e-4)
    assert g["deleted_customers"] == 1


def test_stopped_buying_after_a_reminder(shop):
    keeps = entry(shop, "9000000001", "100")
    stops = entry(shop, "9000000002", "100")
    advance(shop, 7)                         # Sunday 22 Nov reminder goes to both
    entry(shop, "9000000001", "50")          # "keeps" buys again after the reminder
    advance(shop, 20)
    assert metrics(shop)["guardrails"]["reminded_30_days_ago"] == 0  # not 30 days since the reminder yet
    advance(shop, 10)
    g = metrics(shop)["guardrails"]
    assert g["reminded_30_days_ago"] == 2 and g["stopped_buying_on_credit"] == 1 and g["stopped_rate"] == 0.5
    assert keeps != stops


def test_promises_kept_by_source(shop):
    shop.put("/api/settings", json={"reply_parsing_enabled": True})
    a = entry(shop, "9000000001", "100")
    b = entry(shop, "9000000002", "100")
    shop.post(f"/api/customers/{a}/call-outcome", json={"outcome": "promised_date", "promised_date": "2026-11-18"})
    token = shop.get(f"/api/customers/{b}").json()["pay_link"].rsplit("/", 1)[1]
    shop.post(f"/api/sim/phone/{token}/reply", json={"text": "kal dunga"})
    pay(shop, a, "100")  # call promise kept
    advance(shop, 5)     # reply promise broken
    p = metrics(shop)["promises"]
    assert p["call"] == {"total": 1, "kept": 1, "broken": 0, "pending": 0, "kept_rate": 1.0}
    assert p["reply"]["broken"] == 1 and p["reply"]["kept_rate"] == 0.0
    r = metrics(shop)["replies"]
    assert r["received"] == 1 and r["read"] == 1 and r["promise"] == 1 and r["by_rules"] == 1


def test_age_buckets_of_unpaid_money(shop):
    entry(shop, "9000000001", "100")
    advance(shop, 20)
    entry(shop, "9000000002", "200")
    advance(shop, 15)  # bills are now 35 and 15 days old
    o = metrics(shop)["outstanding"]
    assert o["paise"] == 30000 and o["bills"] == 2
    by = {b["label"]: b["paise"] for b in o["buckets"]}
    assert by["15-30 days"] == 20000 and by["31-60 days"] == 10000 and by["0-7 days"] == 0
