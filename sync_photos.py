"""Применяет фото из assets/photos/manifest.json к товарам по названию.

Запускается при старте бота: если у товара нет фото, но для его названия
есть картинка в манифесте — она подставляется автоматически.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import config  # noqa: E402
from core.storage import Storage  # noqa: E402

MANIFEST = config.ROOT / "assets" / "photos" / "manifest.json"


def sync_photos(db: Storage) -> int:
    if not MANIFEST.exists():
        return 0
    try:
        mapping = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return 0
    applied = 0
    for product in db.products(active_only=False):
        if product.get("photo"):
            continue
        path = mapping.get(product["title"])
        if not path:
            continue
        if not (config.ROOT / path).exists():
            continue
        db.set_photo(product["id"], f"file:{path}")
        applied += 1
    return applied


def main() -> int:
    db = Storage(config.DB_PATH)
    count = sync_photos(db)
    print(f"фото применено: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
