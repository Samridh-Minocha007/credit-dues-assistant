"""Setup screen: the shopkeeper approves wording + schedule ONCE.

Editing the wording or the schedule clears the approval, so automatic
reminders can never go out with text the shopkeeper hasn't seen.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import clock
from ..config import settings as app_settings
from ..db import get_db
from ..models import Shop
from ..schemas import SettingsOut, SettingsUpdate
from ..services.money import to_paise
from ..services.shop import get_or_create_shop
from ..services.templates import DEFAULT_TEMPLATES, InvalidTemplate, render, validate_template

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Changing any of these means the shopkeeper must approve again.
NEEDS_REAPPROVAL = {"message_template", "reminder_day", "reminder_time", "message_language"}


def _out(shop: Shop) -> SettingsOut:
    out = SettingsOut.model_validate(shop)
    out.approved = shop.settings_approved_at is not None
    out.reply_reader = "gemini" if app_settings.gemini_api_key else "rules"
    out.demo_mode = app_settings.demo_mode
    out.preview = render(
        shop.message_template, name="Ramesh", shop=shop.name, amount="840", link="https://pay.example/abc123",
        lang=shop.message_language,
    )
    return out


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return _out(get_or_create_shop(db))


@router.put("", response_model=SettingsOut)
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    shop = get_or_create_shop(db)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)

    if "message_template" in changes:
        try:
            validate_template(changes["message_template"])
        except InvalidTemplate as e:
            raise HTTPException(422, str(e))
    # Switching language while still on the standard wording: switch the
    # wording too. A custom wording is left alone (the shopkeeper wrote it).
    new_lang = changes.get("message_language")
    if new_lang and new_lang != shop.message_language and "message_template" not in changes:
        if shop.message_template == DEFAULT_TEMPLATES.get(shop.message_language):
            changes["message_template"] = DEFAULT_TEMPLATES[new_lang]
    if "escalation_amount" in changes:
        changes["escalation_amount_paise"] = to_paise(changes.pop("escalation_amount"))

    if any(k in NEEDS_REAPPROVAL and getattr(shop, k) != v for k, v in changes.items()):
        shop.settings_approved_at = None
    for k, v in changes.items():
        setattr(shop, k, v)
    db.commit()
    return _out(shop)


@router.post("/approve", response_model=SettingsOut)
def approve_settings(db: Session = Depends(get_db)):
    shop = get_or_create_shop(db)
    shop.settings_approved_at = clock.now()
    db.commit()
    return _out(shop)
