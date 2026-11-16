from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect, text

from app import clock
from app.services.guardrails import in_quiet_hours, next_allowed_time

DAY = datetime(2026, 11, 16, 11, 0)    # Monday 11:00, inside shop hours
NIGHT = datetime(2026, 11, 16, 22, 30)  # Monday 22:30, inside quiet hours


def entry(client, phone="9876543210", bill="500", paid="0", name="Ramesh"):
    r = client.post("/api/entries", json={"phone": phone, "bill_amount": bill, "amount_paid": paid, "name": name})
    assert r.status_code == 201, r.text
    return r.json()


def pay_token(client, cid):
    return client.get(f"/api/customers/{cid}").json()["pay_link"].rsplit("/", 1)[1]


# ---------- quiet hours ----------
@pytest.mark.parametrize("hhmm,quiet", [("20:59", False), ("21:00", True), ("23:59", True), ("00:30", True), ("07:59", True), ("08:00", False)])
def test_overnight_quiet_hours(hhmm, quiet):
    h, m = map(int, hhmm.split(":"))
    assert in_quiet_hours(datetime(2026, 1, 1, h, m), "21:00", "08:00") is quiet


def test_next_allowed_time():
    assert next_allowed_time(NIGHT, "21:00", "08:00") == datetime(2026, 11, 17, 8, 0)  # tomorrow morning
    assert next_allowed_time(datetime(2026, 11, 17, 6, 0), "21:00", "08:00") == datetime(2026, 11, 17, 8, 0)  # same day
    assert next_allowed_time(DAY, "21:00", "08:00") == DAY


# ---------- bill notice ----------
def test_entry_sends_bill_notice_with_link(client):
    clock.set_now(DAY)
    client.put("/api/settings", json={"upi_id": "sharmastore@okaxis"})
    e = entry(client, bill="500", paid="100")
    msg = e["message"]
    assert msg["kind"] == "bill_notice" and msg["status"] == "sent_sim"
    assert "Rs 400 on credit" in msg["body"] and "Total pending: Rs 400" in msg["body"]
    assert "/pay/" in msg["body"] and "Reply STOP" in msg["body"]
    # Phone number must never appear in the link.
    assert "9876543210" not in msg["body"]


def test_bill_notice_without_upi_id_says_pay_at_shop(client):
    clock.set_now(DAY)
    body = entry(client)["message"]["body"]
    assert "pay at the shop" in body and "/pay/" not in body


def test_bill_notice_at_night_is_held_until_morning(client):
    clock.set_now(NIGHT)
    msg = entry(client)["message"]
    assert msg["status"] == "scheduled"
    assert msg["scheduled_for"] == "2026-11-17T08:00:00"
    assert msg["sent_at"] is None


def test_outbox_lists_newest_first_with_customer(client):
    clock.set_now(DAY)
    entry(client, phone="9000000001", name="Asha")
    clock.advance(hours=1)
    entry(client, phone="9000000002", name="Bharat")
    rows = client.get("/api/messages").json()
    assert [r["customer_name"] for r in rows] == ["Bharat", "Asha"]
    cid = rows[1]["customer_id"]
    assert len(client.get("/api/messages", params={"customer_id": cid}).json()) == 1


# ---------- payments ----------
def test_payment_clears_oldest_due_first(client):
    clock.set_now(DAY)
    first = entry(client, bill="300")
    clock.advance(days=3)
    entry(client, bill="200")
    cid = first["customer"]["id"]

    clock.advance(days=1)
    r = client.post(f"/api/customers/{cid}/payments", json={"amount": "350"})
    assert r.status_code == 200, r.text
    assert r.json()["balance_paise"] == 15000
    assert r.json()["receipt"]["kind"] == "payment_receipt"

    dues = client.get(f"/api/customers/{cid}").json()["dues"]  # newest first
    newer, older = dues
    assert older["status"] == "paid" and older["balance_paise"] == 0
    assert older["closed_at"] == "2026-11-20T11:00:00"
    assert newer["status"] == "open" and newer["balance_paise"] == 15000


def test_pay_link_page_prefills_shop_upi(client):
    clock.set_now(DAY)
    client.put("/api/settings", json={"upi_id": "SharmaStore@okaxis", "name": "Sharma Store"})
    e = entry(client, bill="250")
    cid = e["customer"]["id"]
    page = client.get(f"/api/pay/{pay_token(client, cid)}").json()
    assert page["shop_upi_id"] == "sharmastore@okaxis"  # stored lower-case
    assert page["balance_paise"] == 25000
    assert page["upi_link"] == (
        f"upi://pay?pa=sharmastore@okaxis&pn=Sharma%20Store&am=250.00&cu=INR&tn=Ramesh%20dues%20C{cid}"
    )
    assert "phone" not in page


def test_cash_payment_validation(client):
    clock.set_now(DAY)
    cid = entry(client, bill="100")["customer"]["id"]
    r = client.post(f"/api/customers/{cid}/payments", json={"amount": "101"})
    assert r.status_code == 422 and "more than the pending" in r.text
    assert client.post(f"/api/customers/{cid}/payments", json={"amount": "0"}).status_code == 422
    client.post(f"/api/customers/{cid}/payments", json={"amount": "100"})
    assert "Nothing is pending" in client.post(f"/api/customers/{cid}/payments", json={"amount": "1"}).text


def test_bad_token_is_404(client):
    assert client.get("/api/pay/not-a-real-token").status_code == 404


def test_each_customer_gets_a_different_link(client):
    a = entry(client, phone="9000000001")["customer"]["id"]
    b = entry(client, phone="9000000002")["customer"]["id"]
    assert pay_token(client, a) != pay_token(client, b)


# ---------- upgrading a slice-1 database ----------
def test_upgrade_adds_pay_token_to_old_database(tmp_path):
    from app.upgrade import upgrade
    from app.db import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:  # the slice-1 customers table, without pay_token
        conn.execute(text(
            "CREATE TABLE customers (id INTEGER PRIMARY KEY, shop_id INTEGER, phone VARCHAR(10), name VARCHAR(100),"
            " consent_at DATETIME, consent_method VARCHAR(40), opted_out_at DATETIME, created_at DATETIME)"
        ))
        conn.execute(text("INSERT INTO customers VALUES (1, 1, '9876543210', 'Old', '2026-11-01', 'given_to_shopkeeper', NULL, '2026-11-01')"))
    Base.metadata.create_all(engine)
    upgrade(engine)
    upgrade(engine)  # safe to run twice
    assert "pay_token" in {c["name"] for c in inspect(engine).get_columns("customers")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT pay_token FROM customers")).scalar()
