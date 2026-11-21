"""Customer messages in Hindi."""
from datetime import date, datetime

from app import clock
from app.services import templates


def test_hindi_templates():
    assert templates.format_day(date(2026, 12, 19), "hi") == "शनिवार 19 दिसंबर"
    msg = templates.bill_notice(name="Ramesh", shop="Sharma Store", credit="400", total="900", link="L", lang="hi")
    assert msg.startswith("नमस्ते Ramesh जी") and "₹400" in msg and "STOP" in msg
    assert "हिसाब साफ़" in templates.payment_receipt(name=None, shop="S", paid="100", remaining="0", lang="hi")
    assert templates.render(templates.DEFAULT_TEMPLATES["hi"], name=None, shop="S", amount="50", link="L", lang="hi").startswith("नमस्ते जी")


def test_switching_to_hindi_swaps_default_wording_and_needs_reapproval(client):
    clock.set_now(datetime(2026, 11, 17, 11, 0))
    client.post("/api/settings/approve")
    s = client.put("/api/settings", json={"message_language": "hi"}).json()
    assert s["message_language"] == "hi" and s["approved"] is False
    assert s["message_template"] == templates.DEFAULT_TEMPLATES["hi"]
    assert s["preview"].startswith("नमस्ते Ramesh जी")


def test_custom_wording_is_kept_when_switching(client):
    custom = "Hello {name}, Rs {amount} pending. Pay: {link}"
    client.put("/api/settings", json={"message_template": custom})
    assert client.put("/api/settings", json={"message_language": "hi"}).json()["message_template"] == custom


def test_messages_go_out_in_hindi(client):
    clock.set_now(datetime(2026, 11, 17, 11, 0))
    client.put("/api/settings", json={"message_language": "hi", "upi_id": "shop@okaxis"})
    r = client.post("/api/entries", json={"phone": "9876543210", "bill_amount": "500", "name": "Ramesh"}).json()
    assert "उधार" in r["message"]["body"]


def test_invalid_language_rejected(client):
    assert client.put("/api/settings", json={"message_language": "fr"}).status_code == 422
