"""Shop sign-up, login and logout (used in pilot mode)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..services.auth import AuthError, login, logout, signup
from ..services.phone import InvalidPhone
from ..services.shop import get_or_create_shop

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupIn(BaseModel):
    shop_name: str = Field(min_length=1, max_length=100)
    phone: str
    pin: str


class LoginIn(BaseModel):
    phone: str
    pin: str


def _bearer(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    return h[7:].strip() if h.lower().startswith("bearer ") else None


@router.get("/me")
def me(db: Session = Depends(get_db)):
    """Is login required, and which shop is this? (The auth step has already run.)"""
    from ..services.shop import current_shop_id

    logged_in = current_shop_id.get() is not None
    if settings.auth_required and not logged_in:
        return {"auth_required": True, "logged_in": False}
    shop = get_or_create_shop(db)
    return {"auth_required": settings.auth_required, "logged_in": logged_in, "shop_id": shop.id, "shop_name": shop.name}


@router.post("/signup", status_code=201)
def do_signup(body: SignupIn, db: Session = Depends(get_db)):
    try:
        shop, token = signup(db, shop_name=body.shop_name, phone=body.phone, pin=body.pin)
    except (AuthError, InvalidPhone) as e:
        raise HTTPException(422, str(e))
    return {"token": token, "shop_id": shop.id, "shop_name": shop.name}


@router.post("/login")
def do_login(body: LoginIn, db: Session = Depends(get_db)):
    try:
        shop, token = login(db, phone=body.phone, pin=body.pin)
    except AuthError as e:
        raise HTTPException(401, str(e))
    return {"token": token, "shop_id": shop.id, "shop_name": shop.name}


@router.post("/logout")
def do_logout(request: Request, db: Session = Depends(get_db)):
    token = _bearer(request)
    if token:
        logout(db, token)
    return {"ok": True}
