"""Сборка всех ассетов магазина одной командой.

Запуск: python make_assets.py
Создаёт паки, обложки, виджет для OBS и возвращает готовые архивы в assets/.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILDERS = [
    ("pack_builder/build_pack.py", "базовый OBS-пак"),
    ("pack_builder/build_more_packs.py", "Twitch, обложки, аим-тренажёр"),
    ("pack_builder/build_catalog.py", "алерты, экраны, панели, звуки, гайды"),
    ("pack_builder/build_bot_ad.py", "рекламный GIF для OBS"),
]


def main() -> int:
    for script, title in BUILDERS:
        path = ROOT / script
        if not path.exists():
            print(f"пропуск: {script} не найден")
            continue
        print(f"\n=== {title} ===")
        result = subprocess.run([sys.executable, str(path)], cwd=ROOT)
        if result.returncode != 0:
            print(f"ошибка в {script}")
            return result.returncode
    print("\nГотово. Ассеты в папке assets/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
