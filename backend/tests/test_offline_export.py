"""Offline entries (no duplicates, real sale time) and CSV export."""
from datetime import datetime

from app import clock

NOW = datetime(2026, 11, 16, 18, 0)


def test_offline_entry_synced_twice_is_saved_once(client):
    clock.set_now(NOW)
    body = {"phone": "9876543210", "bill_amount": "300", "client_ref": "phone-abc-1", "recorded_at": "2026-11-16T15:30:00"}
    first = client.post("/api/entries", json=body)
    again = client.post("/api/entries", json=body)  # the sync was retried
    assert first.status_code == 201 and again.status_code == 201
    assert first.json()["due"]["id"] == again.json()["due"]["id"]
    cid = first.json()["customer"]["id"]
    d = client.get(f"/api/customers/{cid}").json()
    assert len(d["dues"]) == 1 and d["dues"][0]["created_at"] == "2026-11-16T15:30:00"


def test_unbelievable_sale_time_is_ignored(client):
    clock.set_now(NOW)
    for when in ("2026-11-17T10:00:00", "2026-10-01T10:00:00"):  # future, too old
        r = client.post("/api/entries", json={"phone": "9876543210", "bill_amount": "100", "recorded_at": when}).json()
        assert r["due"]["created_at"] == "2026-11-16T18:00:00"


def test_csv_export(client):
    clock.set_now(NOW)
    cid = client.post("/api/entries", json={"phone": "9876543210", "bill_amount": "500", "name": "रमेश"}).json()["customer"]["id"]
    client.post(f"/api/customers/{cid}/payments", json={"amount": "200"})
    r = client.get("/api/export/ledger.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8-sig").strip().splitlines()
    assert text[0] == "date,customer,phone,type,details,amount_rupees,customer_balance_rupees"
    assert text[1].endswith(",bill,,500.00,500.00") and "रमेश" in text[1]
    assert text[2].endswith(",payment,cash,-200.00,300.00")
