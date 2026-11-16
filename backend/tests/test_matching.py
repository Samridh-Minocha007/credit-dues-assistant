"""Matching UPI payments (made to the shop's single UPI ID) to customers."""
from datetime import datetime

import pytest

from app import clock

DAY = datetime(2026, 11, 16, 11, 0)


@pytest.fixture
def shop(client):
    clock.set_now(DAY)
    client.put("/api/settings", json={"upi_id": "sharmastore@okaxis", "name": "Sharma Store"})
    return client


def entry(client, phone, bill, name):
    r = client.post("/api/entries", json={"phone": phone, "bill_amount": bill, "name": name})
    return r.json()["customer"]["id"]


def bank(client, amount, vpa="9876543210@ybl", name="RAMESH KUMAR", note=None):
    r = client.post("/api/sim/bank-notification", json={"payer_vpa": vpa, "payer_name": name, "amount": amount, "note": note})
    assert r.status_code == 201, r.text
    return r.json()


def balance(client, cid):
    return client.get(f"/api/customers/{cid}").json()["balance_paise"]


# ---------- strong evidence: auto-match ----------
def test_note_reference_auto_matches_and_sends_receipt(shop):
    cid = entry(shop, "9876543210", "750", "Ramesh")
    inc = bank(shop, "300", note=f"Ramesh dues C{cid}")
    assert inc["status"] == "matched_auto" and inc["customer_id"] == cid
    assert "reference" in inc["match_reason"]
    assert balance(shop, cid) == 45000
    detail = shop.get(f"/api/customers/{cid}").json()
    assert detail["payments"][0]["source"] == "upi"
    assert detail["messages"][0]["kind"] == "payment_receipt"


def test_upi_id_is_learned_from_note_match(shop):
    cid = entry(shop, "9876543210", "750", "Ramesh")
    bank(shop, "100", note=f"Ramesh dues C{cid}")
    # Next time the customer clears the note: still matched by UPI ID.
    inc = bank(shop, "200", note=None)
    assert inc["status"] == "matched_auto" and "known UPI ID" in inc["match_reason"]
    assert balance(shop, cid) == 45000


def test_note_beats_learned_upi_id(shop):
    """A parent who usually pays their own tab pays their child's tab via the child's link."""
    parent = entry(shop, "9000000001", "500", "Asha")
    child = entry(shop, "9000000002", "300", "Ravi")
    bank(shop, "100", vpa="asha@okicici", name="ASHA", note=f"Asha dues C{parent}")
    inc = bank(shop, "300", vpa="asha@okicici", name="ASHA", note=f"Ravi dues C{child}")
    assert inc["customer_id"] == child and balance(shop, child) == 0


# ---------- strong evidence that doesn't fit: ask ----------
def test_paying_more_than_owed_asks_shopkeeper(shop):
    cid = entry(shop, "9876543210", "200", "Ramesh")
    inc = bank(shop, "500", note=f"Ramesh dues C{cid}")
    assert inc["status"] == "needs_review" and "more than" in inc["match_reason"]
    assert balance(shop, cid) == 20000  # untouched until confirmed


def test_possible_double_payment_asks_shopkeeper(shop):
    cid = entry(shop, "9876543210", "200", "Ramesh")
    bank(shop, "200", note=f"Ramesh dues C{cid}")
    inc = bank(shop, "200", vpa="other@ybl", note=f"Ramesh dues C{cid}")
    assert inc["status"] == "needs_review" and "paid twice" in inc["match_reason"]


def test_known_upi_id_with_nothing_pending_is_a_regular_sale(shop):
    cid = entry(shop, "9876543210", "200", "Ramesh")
    bank(shop, "200", note=f"Ramesh dues C{cid}")
    inc = bank(shop, "80")  # same UPI ID, buying today's groceries
    assert inc["status"] == "not_dues"


# ---------- weak evidence: suggest, never auto ----------
def test_exact_amount_suggests_but_does_not_mark(shop):
    cid = entry(shop, "9876543210", "640", "Ramesh")
    inc = bank(shop, "640", vpa="stranger@ybl", name="SOMEONE")
    assert inc["status"] == "needs_review" and inc["customer_id"] == cid
    assert "amount matches" in inc["match_reason"]
    assert balance(shop, cid) == 64000


def test_name_match_suggests(shop):
    cid = entry(shop, "9876543210", "640", "Ramesh")
    inc = bank(shop, "100", vpa="rk@paytm", name="RAMESH K")
    assert inc["status"] == "needs_review" and inc["customer_id"] == cid


def test_two_possible_customers_lists_both(shop):
    entry(shop, "9000000001", "300", "Asha")
    entry(shop, "9000000002", "300", "Bharat")
    inc = bank(shop, "300", vpa="x@ybl", name="X")
    assert inc["status"] == "needs_review" and inc["customer_id"] is None
    assert "Asha" in inc["match_reason"] and "Bharat" in inc["match_reason"]


def test_unrelated_payment_is_left_alone(shop):
    entry(shop, "9876543210", "640", "Ramesh")
    inc = bank(shop, "45", vpa="walkin@ybl", name="PRIYA S")
    assert inc["status"] == "not_dues"
    assert shop.get("/api/incoming-payments", params={"status": "needs_review"}).json() == []


# ---------- shopkeeper confirms / dismisses ----------
def test_confirm_marks_paid_and_learns_upi_id(shop):
    cid = entry(shop, "9876543210", "640", "Ramesh")
    inc = bank(shop, "640", vpa="rk@paytm", name="R K")
    r = shop.post(f"/api/incoming-payments/{inc['id']}/confirm", json={"customer_id": cid})
    assert r.status_code == 200 and r.json()["status"] == "matched_confirmed"
    assert balance(shop, cid) == 0
    entry(shop, "9876543210", "100", "Ramesh")
    assert bank(shop, "100", vpa="rk@paytm", name="R K")["status"] == "matched_auto"


def test_confirm_overpayment_applies_only_whats_owed(shop):
    cid = entry(shop, "9876543210", "200", "Ramesh")
    inc = bank(shop, "500", note=f"Ramesh dues C{cid}")
    r = shop.post(f"/api/incoming-payments/{inc['id']}/confirm", json={"customer_id": cid}).json()
    assert "Rs 200 applied" in r["match_reason"]
    assert balance(shop, cid) == 0


def test_confirm_twice_and_dismiss_after_match_rejected(shop):
    cid = entry(shop, "9876543210", "640", "Ramesh")
    inc = bank(shop, "640", vpa="rk@paytm", name="R K")
    shop.post(f"/api/incoming-payments/{inc['id']}/confirm", json={"customer_id": cid})
    assert shop.post(f"/api/incoming-payments/{inc['id']}/confirm", json={"customer_id": cid}).status_code == 422
    assert shop.post(f"/api/incoming-payments/{inc['id']}/dismiss").status_code == 422


def test_dismiss(shop):
    entry(shop, "9876543210", "640", "Ramesh")
    inc = bank(shop, "640", vpa="rk@paytm", name="R K")
    r = shop.post(f"/api/incoming-payments/{inc['id']}/dismiss").json()
    assert r["status"] == "not_dues" and r["customer_id"] is None


# ---------- settings + phone ----------
def test_upi_id_validation(client):
    assert client.put("/api/settings", json={"upi_id": "not-a-upi"}).status_code == 422
    assert client.put("/api/settings", json={"upi_id": " Shop@OKAXIS "}).json()["upi_id"] == "shop@okaxis"


def test_phone_view_shows_chat_oldest_first(shop):
    cid = entry(shop, "9876543210", "300", "Ramesh")
    bank(shop, "100", note=f"Ramesh dues C{cid}")
    token = shop.get(f"/api/customers/{cid}").json()["pay_link"].rsplit("/", 1)[1]
    phone = shop.get(f"/api/sim/phone/{token}").json()
    assert phone["shop_name"] == "Sharma Store"
    assert [m["kind"] for m in phone["messages"]] == ["bill_notice", "payment_receipt"]
