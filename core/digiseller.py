"""Партнёрка Digiseller: продажа чужих цифровых товаров со своей витрины.

Схема: вы регистрируетесь продавцом на Digiseller, берёте товары партнёров
(валюта, подписки, ключи), а бот показывает их и выдаёт код через их API.

Нужны ключи в .env:
    DIGISELLER_SELLER_ID=...
    DIGISELLER_API_KEY=...

Модуль намеренно тонкий: проверка ключей и базовые запросы. Эндпоинты
Digiseller меняются, поэтому перед запуском прогоните `python -m core.digiseller`.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from . import config

API = "https://api.digiseller.ru/api"


def ready() -> bool:
    return bool(config.DIGISELLER_SELLER_ID and config.DIGISELLER_API_KEY)


def _headers() -> dict:
    raw = f"{config.DIGISELLER_SELLER_ID}:{config.DIGISELLER_API_KEY}".encode("utf-8")
    return {
        "Authorization": "Basic " + base64.b64encode(raw).decode("ascii"),
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "FrolikShop/1.0",
    }


def _get(path: str, params: dict | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def categories() -> dict:
    return _get("/categories")


def products(page: int = 1, rows: int = 20) -> dict:
    return _get("/products/list", {
        "seller_id": config.DIGISELLER_SELLER_ID,
        "page": page,
        "rows": rows,
        "currency": "RUB",
    })


def product_info(product_id: int) -> dict:
    return _get("/products/info", {
        "seller_id": config.DIGISELLER_SELLER_ID,
        "product_id": product_id,
        "locale": "ru-RU",
    })


def check() -> tuple[bool, str]:
    """Проверка ключей: без ключей — понятное сообщение."""
    if not ready():
        return False, "Ключи Digiseller не заданы в .env"
    try:
        data = categories()
        return True, f"Связь есть, категорий: {len(data.get('categories') or data.get('data') or [])}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: ключи не приняты"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


if __name__ == "__main__":
    ok, message = check()
    print(("✓ " if ok else "✗ ") + message)
