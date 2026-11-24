"""Настройки магазина."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
DATA.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)
DB_PATH = DATA / "shop.db"


def load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = {
    int(x) for x in os.environ.get("ADMIN_IDS", "").replace(";", ",").split(",")
    if x.strip().isdigit()
}

SHOP_NAME = os.environ.get("SHOP_NAME", "Frolik Shop")

# manual — оплата по реквизитам с подтверждением админом
# yookassa — автоматическая оплата картой/СБП через ЮKassa
PAYMENT_MODE = os.environ.get("PAYMENT_MODE", "manual").lower()

PAY_CARD = os.environ.get("PAY_CARD", "")
PAY_SBP = os.environ.get("PAY_SBP", "")          # телефон или ссылка СБП
PAY_NAME = os.environ.get("PAY_NAME", "")
PAY_NOTE = os.environ.get("PAY_NOTE", "В комментарии к переводу укажите номер заказа.")

YOOKASSA_SHOP_ID = os.environ.get("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET = os.environ.get("YOOKASSA_SECRET", "")
RETURN_URL = os.environ.get("RETURN_URL", "")

# Партнёрка Digiseller: продажа чужих цифровых товаров со своей витрины
DIGISELLER_SELLER_ID = os.environ.get("DIGISELLER_SELLER_ID", "")
DIGISELLER_API_KEY = os.environ.get("DIGISELLER_API_KEY", "")

MAX_ITEMS_PER_ADD = 500
ORDER_TTL_MINUTES = int(os.environ.get("ORDER_TTL_MINUTES", "120"))
