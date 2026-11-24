"""Наполнение пустой базы товарами из products_seed.json.

Вызывается автоматически при старте бота, если каталог пуст.
Можно запустить вручную: python seed_products.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import config  # noqa: E402
from core.storage import Storage  # noqa: E402

SEED = Path(__file__).resolve().parent / "products_seed.json"


def seed_if_empty(db: Storage) -> int:
    if db.products(active_only=False):
        return 0
    if not SEED.exists():
        return 0
    data = json.loads(SEED.read_text(encoding="utf-8"))
    added = 0
    for item in data:
        pid = db.add_product(item["title"], item.get("description", ""), int(item["price"]),
                             category=item.get("category", "Разное"))
        items = item.get("items") or []
        if items:
            db.add_stock(pid, items)
        photo = item.get("photo") or ""
        if photo and (config.ROOT / photo).exists():
            db.set_photo(pid, f"file:{photo}")
        if not item.get("active", True):
            db.set_active(pid, False)
        added += 1
    return added


def main() -> int:
    db = Storage(config.DB_PATH)
    count = seed_if_empty(db)
    if count:
        print(f"добавлено товаров: {count}")
    else:
        print("каталог уже заполнен — пропуск")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
