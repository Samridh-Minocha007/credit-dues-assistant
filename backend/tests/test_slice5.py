"""Reading promises from customer replies (the experiment)."""
from datetime import date, datetime

import pytest

from app import clock
from app.services import reply_parser
from app.services.reply_parser import ParsedReply, _check_gemini_answer, parse_reply, parse_with_rules

TUESDAY = date(2026, 11, 17)


# ---------- rule-based reader ----------
@pytest.mark.parametrize("text,expected", [
    ("kal dunga", date(2026, 11, 18)),
    ("Kal de dunga bhaiya", date(2026, 11, 18)),
    ("tomorrow", date(2026, 11, 18)),
    ("parso bhej dunga", date(2026, 11, 19)),
    ("aaj shaam tak", date(2026, 11, 17)),
    ("will pay Friday", date(2026, 11, 20)),
    ("shukravar ko dunga", date(2026, 11, 20)),
    ("tuesday", date(2026, 11, 17)),  # said on a Tuesday: today
    ("monday ko pakka", date(2026, 11, 23)),
    ("agle hafte", date(2026, 11, 24)),
    ("next week I will pay", date(2026, 11, 24)),
    ("3 din me de dunga", date(2026, 11, 20)),
    ("in 5 days", date(2026, 11, 22)),
    ("1 tarikh ko salary aayegi tab", date(2026, 12, 1)),
    ("will pay on 25th", date(2026, 11, 25)),
    ("month end tak", date(2026, 11, 30)),
    ("कल दूंगा", date(2026, 11, 18)),
    ("परसों दे दूंगा", date(2026, 11, 19)),
])
def test_rules_find_the_promised_date(text, expected):
    r = parse_with_rules(text, TUESDAY)
    assert r.intent == "promise" and r.promised_date == expected and r.is_usable_promise


@pytest.mark.parametrize("text,intent", [
    ("kal de diya tha", "already_paid"),  # "kal" here means yesterday
    ("paid already", "already_paid"),
    ("bhej diya", "already_paid"),
    ("kal nahi de paunga", "other"),
    ("jaldi dunga", "other"),  # no day: too vague to set a follow-up
    ("ok", "other"),
    ("who is this", "other"),
    ("money tight hai", "other"),  # "mon" inside "money" must not count as Monday
])
def test_rules_dont_invent_promises(text, intent):
    r = parse_with_rules(text, TUESDAY)
    assert r.intent == intent and not r.is_usable_promise


def test_date_without_paying_word_is_less_certain():
    assert parse_with_rules("friday ko", TUESDAY).confidence < parse_with_rules("friday ko dunga", TUESDAY).confidence


def test_dates_too_far_ahead_are_ignored():
    assert parse_with_rules("90 din baad", TUESDAY).intent == "other"


# ---------- Gemini answers are checked, never trusted blindly ----------
def test_good_gemini_answer_is_used():
    r = _check_gemini_answer({"intent": "promise", "promised_date": "2026-11-21", "confidence": 0.92}, TUESDAY)
    assert r == ParsedReply("promise", date(2026, 11, 21), 0.92, "gemini")


@pytest.mark.parametrize("answer", [
    {"intent": "promise", "promised_date": "2026-11-10", "confidence": 0.9},  # in the past
    {"intent": "promise", "promised_date": "2027-06-01", "confidence": 0.9},  # too far ahead
    {"intent": "promise", "promised_date": "next friday", "confidence": 0.9},  # not a date
    {"intent": "maybe", "confidence": 0.9},
    {"intent": "promise", "promised_date": "2026-11-20", "confidence": "high"},
])
def test_bad_gemini_answers_are_rejected(answer):
    assert _check_gemini_answer(answer, TUESDAY) is None


def test_falls_back_to_rules_when_gemini_fails(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "test-key")

    def broken(text, today):
        raise TimeoutError("network down")

    monkeypatch.setattr(reply_parser, "ask_gemini", broken)
    r = parse_reply("kal dunga", TUESDAY)
    assert r.parsed_by == "rules" and r.promised_date == date(2026, 11, 18)


def test_uses_gemini_when_key_is_set(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(reply_parser, "ask_gemini", lambda text, today: ParsedReply("promise", date(2026, 12, 1), 0.9, "gemini"))
    assert parse_reply("salary aate hi de dunga", TUESDAY).parsed_by == "gemini"


# ---------- the experiment end to end ----------
@pytest.fixture
def shop(client):
    clock.set_now(datetime(2026, 11, 17, 11, 0))
    client.put("/api/settings", json={"upi_id": "sharmastore@okaxis", "name": "Sharma Store"})
    client.post("/api/settings/approve")
    client.post("/api/dev/run-scheduler")
    return client


def setup_customer(client, bill="500"):
    cid = client.post("/api/entries", json={"phone": "9876543210", "bill_amount": bill, "name": "Ramesh"}).json()["customer"]["id"]
    token = client.get(f"/api/customers/{cid}").json()["pay_link"].rsplit("/", 1)[1]
    return cid, token


def reply(client, token, text):
    return client.post(f"/api/sim/phone/{token}/reply", json={"text": text}).json()


def test_experiment_off_replies_are_only_stored(shop):
    cid, token = setup_customer(shop)
    reply(shop, token, "kal dunga")
    d = shop.get(f"/api/customers/{cid}").json()
    assert d["promises"] == [] and d["collection_state"] == "reminders"
    assert d["messages"][0]["parsed"] is None


def test_experiment_on_promise_is_recorded_and_acknowledged(shop):
    shop.put("/api/settings", json={"reply_parsing_enabled": True})
    cid, token = setup_customer(shop)
    chat = reply(shop, token, "parso de dunga")
    assert chat["messages"][-1]["body"].startswith("Thank you! Sharma Store has noted that you'll pay by Thursday 19 November")
    d = shop.get(f"/api/customers/{cid}").json()
    p = d["promises"][0]
    assert p["source"] == "reply" and p["promised_date"] == "2026-11-19" and p["raw_text"] == "parso de dunga"
    assert p["parsed_by"] == "rules" and p["status"] == "pending"
    assert d["collection_state"] == "promised"
    inbound = [m for m in d["messages"] if m["direction"] == "in"][0]
    assert '"intent": "promise"' in inbound["parsed"]


def test_promise_from_reply_gets_followup_and_breaks_if_unpaid(shop):
    shop.put("/api/settings", json={"reply_parsing_enabled": True})
    cid, token = setup_customer(shop)
    reply(shop, token, "kal dunga")
    shop.post("/api/dev/advance", json={"days": 1})  # Wed 11:00, follow-up went at 10:00
    msgs = shop.get(f"/api/customers/{cid}").json()["messages"]
    assert any(m["kind"] == "promise_followup" for m in msgs)
    shop.post("/api/dev/advance", json={"days": 1})
    d = shop.get(f"/api/customers/{cid}").json()
    assert d["promises"][0]["status"] == "broken"
    assert d["collection_state"] == "reminders"  # bill is young: back to weekly reminders, not a call


def test_unclear_reply_does_nothing_automatic(shop):
    shop.put("/api/settings", json={"reply_parsing_enabled": True})
    cid, token = setup_customer(shop)
    chat = reply(shop, token, "jaldi dunga")
    assert chat["messages"][-1]["direction"] == "in"  # no acknowledgement
    d = shop.get(f"/api/customers/{cid}").json()
    assert d["promises"] == [] and '"intent": "other"' in d["messages"][0]["parsed"]


def test_already_paid_claim_is_recorded_for_the_shopkeeper(shop):
    shop.put("/api/settings", json={"reply_parsing_enabled": True})
    cid, token = setup_customer(shop)
    reply(shop, token, "maine kal de diya tha")
    d = shop.get(f"/api/customers/{cid}").json()
    assert d["promises"] == [] and '"intent": "already_paid"' in d["messages"][0]["parsed"]


def test_promise_reply_takes_customer_off_the_call_list(shop):
    shop.put("/api/settings", json={"reply_parsing_enabled": True})
    cid, token = setup_customer(shop)
    shop.post("/api/dev/advance", json={"days": 30})
    assert [c["customer_id"] for c in shop.get("/api/call-list").json()["to_call"]] == [cid]
    reply(shop, token, "friday ko pakka dunga")
    lists = shop.get("/api/call-list").json()
    assert lists["to_call"] == [] and [c["customer_id"] for c in lists["promised"]] == [cid]


def test_stop_still_works_with_experiment_on(shop):
    shop.put("/api/settings", json={"reply_parsing_enabled": True})
    cid, token = setup_customer(shop)
    reply(shop, token, "STOP")
    d = shop.get(f"/api/customers/{cid}").json()
    assert d["opted_out"] is True and d["promises"] == []


def test_settings_say_which_reader_is_active(shop):
    assert shop.get("/api/settings").json()["reply_reader"] == "rules"
