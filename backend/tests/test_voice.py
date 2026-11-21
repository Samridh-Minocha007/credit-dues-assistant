"""Voice entry: speech-to-text output -> filled form."""
from types import SimpleNamespace as C

import pytest

from app.services.voice import parse_voice

PEOPLE = [C(id=1, name="Ramesh Kumar", phone="9876543210"), C(id=2, name="Sita Devi", phone="9811122233"),
          C(id=3, name="Suresh Jain", phone="9000000001"), C(id=4, name="Sunita", phone="9000000002")]


@pytest.mark.parametrize("text,bill,paid", [
    ("Ramesh 500", 500, None),
    ("Ramesh paanch sau udhaar", 500, None),
    ("Ramesh paanch sau, do sau diye", 500, 200),
    ("ramesh 750 paid 250", 750, 250),
    ("Ramesh dedh hazaar", 1500, None),
    ("Ramesh dhai sau", 250, None),
    ("Ramesh saadhe teen sau", 350, None),
    ("Ramesh do hazaar paanch sau", 2500, None),
    ("Ramesh five hundred", 500, None),
    ("रमेश पांच सौ", 500, None),
])
def test_amounts(text, bill, paid):
    r = parse_voice(text, PEOPLE)
    assert (r.bill, r.paid) == (bill, paid)


def test_name_matches_one_customer():
    r = parse_voice("Sita 450", PEOPLE)
    assert r.customer_id == 2 and r.phone == "9811122233" and r.name == "Sita Devi"


def test_two_possible_customers_are_offered_not_guessed():
    r = parse_voice("Su 300", PEOPLE)
    assert r.customer_id is None and {c["id"] for c in r.candidates} == {3, 4}


def test_new_name_is_kept_for_a_new_customer():
    r = parse_voice("Mohan 120", PEOPLE)
    assert r.customer_id is None and r.name == "Mohan" and r.candidates == []


def test_phone_number_spoken_as_digits():
    r = parse_voice("98765 43210 300 udhaar", PEOPLE)
    assert r.phone == "9876543210" and r.customer_id == 1 and r.bill == 300


def test_do_as_a_word_is_not_two():
    assert parse_voice("Ramesh 400 likh do", PEOPLE).bill == 400


def test_endpoint(client):
    client.post("/api/entries", json={"phone": "9876543210", "bill_amount": "100", "name": "Ramesh Kumar"})
    r = client.post("/api/entries/parse-voice", json={"text": "Ramesh paanch sau do sau diye"}).json()
    assert r["bill"] == 500 and r["paid"] == 200 and r["phone"] == "9876543210"
