"""Shop login for pilots: phone number + a 4-6 digit PIN.

- The PIN is never stored. We store a salted PBKDF2 hash (200,000 rounds of
  SHA-256), which is slow on purpose, so a stolen database can't be used
  to try every PIN quickly.
- Logging in returns a random session token (like a temporary key). The
  browser sends it with every request. We store only a SHA-256 hash of the
  token, so the database alone can't be used to log in.
- Wrong PINs are counted; after 5 in a row the account waits 15 minutes,
  so nobody can guess the 10,000 possible 4-digit PINs one by one.
"""
import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Shop, ShopSession
from .phone import normalize_phone

ROUNDS = 200_000
MAX_FAILS = 5
LOCKOUT = timedelta(minutes=15)


class AuthError(ValueError):
    pass


def _hash_pin(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, ROUNDS).hex()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _check_pin_format(pin: str) -> None:
    if not re.fullmatch(r"\d{4,6}", pin or ""):
        raise AuthError("PIN must be 4 to 6 digits")


def _new_session(db: Session, shop: Shop) -> str:
    token = secrets.token_urlsafe(32)
    db.add(ShopSession(shop_id=shop.id, token_hash=_hash_token(token), created_at=clock.now()))
    db.commit()
    return token


def signup(db: Session, *, shop_name: str, phone: str, pin: str) -> tuple[Shop, str]:
    phone = normalize_phone(phone)
    _check_pin_format(pin)
    if db.scalar(select(Shop).where(Shop.owner_phone == phone)):
        raise AuthError("This phone number already has a shop. Log in instead.")
    salt = secrets.token_bytes(16)
    shop = Shop(name=(shop_name or "").strip() or "My Shop", owner_phone=phone, pin_salt=salt.hex(), pin_hash=_hash_pin(pin, salt))
    db.add(shop)
    db.commit()
    return shop, _new_session(db, shop)


def login(db: Session, *, phone: str, pin: str) -> tuple[Shop, str]:
    try:
        phone = normalize_phone(phone)
    except ValueError:
        raise AuthError("Phone number or PIN is wrong")
    shop = db.scalar(select(Shop).where(Shop.owner_phone == phone))
    if shop is None or not shop.pin_hash:
        raise AuthError("Phone number or PIN is wrong")
    now = clock.now()
    if shop.locked_until and shop.locked_until > now:
        raise AuthError("Too many wrong PINs. Try again in 15 minutes.")
    # compare_digest takes the same time whether the first or last character differs.
    if not hmac.compare_digest(_hash_pin(pin or "", bytes.fromhex(shop.pin_salt)), shop.pin_hash):
        shop.failed_logins = (shop.failed_logins or 0) + 1
        if shop.failed_logins >= MAX_FAILS:
            shop.locked_until, shop.failed_logins = now + LOCKOUT, 0
        db.commit()
        raise AuthError("Phone number or PIN is wrong")
    shop.failed_logins, shop.locked_until = 0, None
    db.commit()
    return shop, _new_session(db, shop)


def shop_for_token(db: Session, token: str | None) -> Shop | None:
    if not token:
        return None
    session = db.scalar(select(ShopSession).where(ShopSession.token_hash == _hash_token(token)))
    return db.get(Shop, session.shop_id) if session else None


def logout(db: Session, token: str) -> None:
    session = db.scalar(select(ShopSession).where(ShopSession.token_hash == _hash_token(token)))
    if session:
        db.delete(session)
        db.commit()
