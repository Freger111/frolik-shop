"""Приём рублей: вручную по реквизитам или через ЮKassa."""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Optional

from . import config

YOOKASSA_API = "https://api.yookassa.ru/v3"


def yookassa_ready() -> bool:
    return bool(config.YOOKASSA_SHOP_ID and config.YOOKASSA_SECRET)


def _auth_header() -> str:
    raw = f"{config.YOOKASSA_SHOP_ID}:{config.YOOKASSA_SECRET}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def create_payment(amount: int, order_id: int, description: str) -> Optional[str]:
    """Создаёт платёж и возвращает ссылку на оплату."""
    if not yookassa_ready():
        return None
    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": config.RETURN_URL or "https://t.me",
        },
        "description": description[:128],
        "metadata": {"order_id": str(order_id)},
    }
    req = urllib.request.Request(
        f"{YOOKASSA_API}/payments",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": _auth_header(),
            "Idempotence-Key": f"order-{order_id}",
        })
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data.get("confirmation") or {}).get("confirmation_url")
    except Exception:
        return None


def payment_status(payment_id: str) -> str:
    req = urllib.request.Request(
        f"{YOOKASSA_API}/payments/{payment_id}",
        headers={"Authorization": _auth_header()})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("status", "unknown")
    except Exception:
        return "unknown"
