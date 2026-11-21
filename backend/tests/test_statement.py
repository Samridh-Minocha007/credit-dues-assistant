"""Customer statement: bills and payments with a running balance."""
from datetime import datetime

from app import clock


def test_statement_running_balance_and_send(client):
    clock.set_now(datetime(2026, 11, 16, 11, 0))
    client.put("/api/settings", json={"upi_id": "s@okaxis"})
    cid = client.post("/api/entries", json={"phone": "9876543210", "bill_amount": "500", "amount_paid": "100", "name": "Ramesh",
                                            "items": [{"description": "Atta", "qty": "5 kg"}]}).json()["customer"]["id"]
    clock.advance(days=1)
    client.post(f"/api/customers/{cid}/payments", json={"amount": "150"})
    clock.advance(days=1)
    client.post("/api/entries", json={"phone": "9876543210", "bill_amount": "200"})
    token = client.get(f"/api/customers/{cid}").json()["pay_link"].rsplit("/", 1)[1]

    s = client.get(f"/api/pay/{token}/statement").json()
    assert [(l["kind"], l["amount_paise"], l["balance_paise"]) for l in s["lines"]] == [
        ("bill", 40000, 40000), ("payment", -15000, 25000), ("bill", 20000, 45000)]
    assert s["lines"][0]["text"] == "Atta 5 kg" and s["balance_paise"] == 45000
    assert "phone" not in s

    msg = client.post(f"/api/customers/{cid}/send-statement").json()
    assert msg["kind"] == "statement" and f"/statement/{token}" in msg["body"]


def test_written_off_shows_as_a_line(client):
    clock.set_now(datetime(2026, 11, 16, 11, 0))
    cid = client.post("/api/entries", json={"phone": "9876543210", "bill_amount": "300"}).json()["customer"]["id"]
    client.post(f"/api/customers/{cid}/call-outcome", json={"outcome": "written_off"})
    token = client.get(f"/api/customers/{cid}").json()["pay_link"].rsplit("/", 1)[1]
    lines = client.get(f"/api/pay/{token}/statement").json()["lines"]
    assert [l["kind"] for l in lines] == ["bill", "written_off"] and lines[-1]["balance_paise"] == 0
