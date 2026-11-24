"""Сборка товаров для каталога: алерты, экраны, панели, обложки, аватарки, звуки, гайды.

Запуск: python build_catalog.py
Результат: assets/catalog/<slug>/ и архивы assets/<slug>.zip
"""
from __future__ import annotations

import random
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from build_pack import (CYAN, PURPLE, alert_gif, font, gradient, mix, save_gif, screen,
                        tone, write_wav)
from build_more_packs import cover, panel

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CATALOG = ASSETS / "catalog"


def folder(slug: str) -> Path:
    path = CATALOG / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def zip_dir(path: Path, name: str) -> Path:
    out = ASSETS / f"{name}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in path.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(path.parent))
    return out


# ---------------------------------------------------------------- алерты
def alerts_pack(slug: str, style: str) -> Path:
    root = folder(slug)
    (root / "alerts").mkdir(exist_ok=True)
    if style == "neon":
        items = [
            ("НОВЫЙ ПОДПИСЧИК", "спасибо, что вы с нами", PURPLE),
            ("ДОНАТ", "спасибо за поддержку", CYAN),
            ("ПОДПИСКА", "добро пожаловать в клуб", (255, 92, 160)),
            ("РЕЙД", "к нам пришли зрители", (255, 190, 60)),
            ("ФОЛЛОУ", "теперь ты с нами", (120, 220, 140)),
            ("ХОСТ", "канал передал эфир", (150, 150, 255)),
            ("ТОП ДОНАТ", "это рекорд!", (255, 120, 60)),
            ("ПЕРВЫЙ ЗРИТЕЛЬ", "ты здесь первым", (90, 210, 255)),
        ]
    else:
        items = [
            ("ПОДПИСЧИК", "спасибо", (230, 230, 235)),
            ("ДОНАТ", "спасибо", (200, 200, 210)),
            ("САБ", "добро пожаловать", (190, 190, 200)),
            ("РЕЙД", "привет зрителям", (210, 210, 220)),
            ("ФОЛЛОУ", "спасибо", (220, 220, 230)),
            ("ПОДАРОК", "вау!", (240, 220, 180)),
        ]
    for name, subtitle, color in items:
        fname = name.lower().replace(" ", "_").replace("!", "") + ".gif"
        save_gif(alert_gif(name, subtitle, color), root / "alerts" / fname)
    (root / "README.txt").write_text(
        f"Алерты «{style}»\n"
        "OBS → Источники → Медиа → gif → «Зацикливание» выключить.\n"
        "Звук события можно взять из пака звуков.\n", encoding="utf-8")
    return zip_dir(root, slug)


# ---------------------------------------------------------------- экраны
def screens_pack() -> Path:
    root = folder("screens_cyber")
    (root / "screens").mkdir(exist_ok=True)
    for name, title, sub in (
        ("starting_soon", "СКОРО НАЧНЁМ", "настройка сцены · проверка звука"),
        ("brb", "ОТОШЁЛ", "вернусь через пару минут"),
        ("ending", "СТРИМ ЗАВЕРШЁН", "спасибо за вечер"),
    ):
        img = screen(title, sub)
        # неоновые линии «киберпанк»
        d = ImageDraw.Draw(img)
        for i in range(18):
            y = 780 + i * 16
            d.line([(0, y), (1920, y)], fill=(58, 215, 255, max(0, 60 - i * 3)), width=2)
        img.save(root / "screens" / f"{name}.png")
    (root / "README.txt").write_text(
        "Экраны паузы (1920×1080)\nДобавляются в OBS как изображение на весь экран.\n",
        encoding="utf-8")
    return zip_dir(root, "screens_cyber")


# ---------------------------------------------------------------- панели
DARK_PANELS = [
    ("О СТРИМЕ", "что здесь происходит"),
    ("ДОНАТ", "поддержать эфир"),
    ("РАСПИСАНИЕ", "дни и время"),
    ("СОЦСЕТИ", "telegram · youtube"),
    ("ПРАВИЛА", "уважение прежде всего"),
    ("ЖЕЛЕЗО", "мой сетап"),
    ("МУЗЫКА", "плейлист эфира"),
    ("КОНТАКТ", "по вопросам рекламы"),
]


def panels_pack() -> Path:
    root = folder("panels_dark")
    (root / "panels").mkdir(exist_ok=True)
    for i, (title, sub) in enumerate(DARK_PANELS):
        panel(title, sub, (120, 120, 140)).save(root / "panels" / f"panel_{i + 1}.png")
    (root / "README.txt").write_text(
        "Панели канала 320×100 (8 шт).\n"
        "Twitch → канал → «Изменить панели» → добавить изображение.\n", encoding="utf-8")
    return zip_dir(root, "panels_dark")


# ---------------------------------------------------------------- обложки
def covers_gradient() -> Path:
    root = folder("covers_yt")
    (root / "covers").mkdir(exist_ok=True)
    for i in range(10):
        cover((1280, 720), i % 4, i, with_text=False).save(
            root / "covers" / f"cover_{i + 1:02d}.jpg", quality=90)
    (root / "README.txt").write_text(
        "10 фонов для обложек YouTube 1280×720 без текста.\n"
        "Добавьте заголовок в любом редакторе (Canva, Figma, Paint).\n", encoding="utf-8")
    return zip_dir(root, "covers_yt")


# ---------------------------------------------------------------- аватарки
def avatars_pack() -> Path:
    root = folder("avatars")
    (root / "avatars").mkdir(exist_ok=True)
    palettes = [
        ((124, 92, 255), (58, 215, 255)),
        ((255, 92, 160), (124, 92, 255)),
        ((255, 178, 60), (255, 92, 120)),
        ((60, 200, 140), (58, 215, 255)),
        ((120, 120, 255), (200, 120, 255)),
        ((30, 30, 50), (124, 92, 255)),
    ]
    for i in range(12):
        size = 512
        img = gradient((size, size), *palettes[i % len(palettes)]).convert("RGBA")
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(img, (0, 0), mask)
        d = ImageDraw.Draw(out)
        # геометрический акцент
        k = i % 4
        if k == 0:
            d.ellipse([150, 150, 362, 362], outline=(255, 255, 255, 200), width=10)
        elif k == 1:
            d.polygon([(256, 140), (372, 360), (140, 360)], outline=(255, 255, 255, 200), width=10)
        elif k == 2:
            d.rounded_rectangle([150, 150, 362, 362], radius=40, outline=(255, 255, 255, 200), width=10)
        else:
            d.line([(140, 372), (372, 140)], fill=(255, 255, 255, 200), width=12)
            d.line([(140, 140), (372, 372)], fill=(255, 255, 255, 200), width=12)
        out.save(root / "avatars" / f"avatar_{i + 1:02d}.png")
    (root / "README.txt").write_text(
        "12 аватарок 512×512 PNG с прозрачностью.\n"
        "Подойдут для Twitch, YouTube, Telegram, Discord.\n", encoding="utf-8")
    return zip_dir(root, "avatars")


# ---------------------------------------------------------------- звуки
SOUND_NAMES = [
    "notify_1", "notify_2", "chime_1", "chime_2", "pop_1", "pop_2",
    "click_1", "click_2", "coin_1", "coin_2", "whoosh_1", "whoosh_2",
    "alert_1", "alert_2", "error_1", "success_1", "sub_1", "donate_1",
    "raid_1", "start_1",
]


def sounds_pack() -> Path:
    root = folder("sounds")
    (root / "sounds").mkdir(exist_ok=True)
    rnd = random.Random(11)
    base = {
        "notify": [(880, 0.14), (1240, 0.18)],
        "chime": [(660, 0.2), (990, 0.24), (1320, 0.3)],
        "pop": [(420, 0.08)],
        "click": [(1400, 0.03)],
        "coin": [(1046, 0.06), (1568, 0.16)],
        "whoosh": [(220, 0.3)],
        "alert": [(740, 0.16), (740, 0.16)],
        "error": [(320, 0.25)],
        "success": [(660, 0.12), (880, 0.12), (1100, 0.2)],
        "sub": [(784, 0.14), (1046, 0.2)],
        "donate": [(523, 0.12), (784, 0.2)],
        "raid": [(330, 0.3), (440, 0.3)],
        "start": [(392, 0.18), (523, 0.18), (659, 0.26)],
    }
    for name in SOUND_NAMES:
        key = name.split("_")[0]
        seq = base.get(key, [(600, 0.2)])
        samples: list[float] = []
        for freq, dur in seq:
            sweep = freq * rnd.choice([1.0, 1.25, 0.85])
            samples = mix(samples, tone(freq, dur, vol=0.32, sweep_to=sweep)) if samples \
                else tone(freq, dur, vol=0.32, sweep_to=sweep)
            samples = samples + [0.0] * int(44100 * 0.02)
        write_wav(root / "sounds" / f"{name}.wav", samples)
    (root / "README.txt").write_text(
        "20 звуков для стрима (WAV, 44.1 кГц).\n"
        "OBS → Источники → Медиа → звук события.\n", encoding="utf-8")
    return zip_dir(root, "sounds")


# ---------------------------------------------------------------- гайды
GUIDE_OBS = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>OBS с нуля</title><style>
body{background:#0f1118;color:#e8ecff;font-family:Segoe UI,Arial,sans-serif;max-width:860px;margin:40px auto;padding:0 24px;line-height:1.65}
h1{font-size:34px}h2{color:#3ad7ff;margin-top:30px}code{background:#1b2030;padding:2px 6px;border-radius:6px}
li{margin:6px 0}.tag{background:#7c5cff;padding:4px 10px;border-radius:999px;font-size:13px}
</style></head><body>
<span class="tag">Frolik Shop</span>
<h1>OBS с нуля за 20 минут</h1>
<p>Инструкция для того, кто впервые открыл OBS. Без воды, по шагам.</p>

<h2>1. Установка</h2>
<ol><li>Скачайте OBS Studio с obsproject.com.</li>
<li>Установите, при первом запуске выберите «Оптимизировать для стриминга».</li>
<li>В мастере укажите сервис (Twitch/YouTube) и вставьте ключ трансляции из личного кабинета.</li></ol>

<h2>2. Сцена</h2>
<ol><li>Внизу слева — панель «Сцены». Создайте сцену «Игра».</li>
<li>В «Источниках» нажмите + → «Захват игры» (или «Захват экрана»).</li>
<li>Добавьте «Устройство захвата видео» для камеры.</li>
<li>Добавьте «Аудиовход» для микрофона.</li></ol>

<h2>3. Звук — важнее картинки</h2>
<ul><li>В микшере проверьте уровни: голос −12…−6 дБ, игра −20…−15 дБ.</li>
<li>Включите фильтр «Шумоподавление» на микрофоне (ПКМ → Фильтры).</li>
<li>Добавьте «Компрессор» и «Ограничитель», чтобы не было клиппинга.</li></ul>

<h2>4. Оформление</h2>
<ul><li>Рамка и плашка — из пака, добавляются как «Изображение».</li>
<li>Экран паузы — отдельная сцена, переключайтесь на неё между матчами.</li>
<li>Алерты — через Streamlabs или как «Медиа» с GIF.</li></ul>

<h2>5. Запись и стрим</h2>
<ul><li>Настройки → Вывод: битрейт 4500–6000 кбит/с для 1080p.</li>
<li>Кодек: x264 при слабом ПК, NVENC/AMD при нормальной видеокарте.</li>
<li>Проверьте записью на 2 минуты, посмотрите на дропы.</li></ul>

<h2>Частые проблемы</h2>
<ul><li><b>Тормозит</b> — снизьте разрешение до 720p и битрейт до 3000.</li>
<li><b>Нет звука</b> — проверьте «Аудиовход» и устройство в настройках Windows.</li>
<li><b>Эхо</b> — отключите «Прослушивать с этого устройства» в свойствах микрофона.</li></ul>
</body></html>
"""

GUIDE_PC = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>ПК без тормозов</title><style>
body{background:#0f1118;color:#e8ecff;font-family:Segoe UI,Arial,sans-serif;max-width:860px;margin:40px auto;padding:0 24px;line-height:1.65}
h1{font-size:34px}h2{color:#3ad7ff;margin-top:30px}code{background:#1b2030;padding:2px 6px;border-radius:6px}
pre{background:#151a26;padding:14px;border-radius:10px;overflow:auto}li{margin:6px 0}
.tag{background:#7c5cff;padding:4px 10px;border-radius:999px;font-size:13px}
</style></head><body>
<span class="tag">Frolik Shop</span>
<h1>ПК без тормозов</h1>
<p>10 шагов, которые дают прирост без переустановки Windows. Делайте по порядку.</p>

<h2>1. Посмотрите, что грузит систему</h2>
<pre>Ctrl+Shift+Esc → Диспетчер задач → вкладка «Процессы»</pre>
<p>Сортировка по ЦП и по памяти. Всё, что выше 10% — разбираем.</p>

<h2>2. Автозагрузка</h2>
<pre>Диспетчер задач → вкладка «Автозагрузка» → отключить всё лишнее</pre>
<p>Оставьте антивирус и драйверы. Discord/Steam/Telegram могут запускаться вручную.</p>

<h2>3. Место на диске</h2>
<pre>Win+R → %TEMP% → удалить всё
Win+R → cleanmgr → очистка диска</pre>
<p>Держите на системном диске минимум 15% свободного места.</p>

<h2>4. Визуальные эффекты</h2>
<pre>Win+R → sysdm.cpl → Дополнительно → Быстродействие → «Обеспечить наибольшее быстродействие»</pre>

<h2>5. Электропитание</h2>
<pre>Панель управления → Электропитание → «Высокая производительность»</pre>

<h2>6. Драйвер видеокарты</h2>
<p>Только с сайта производителя (NVIDIA/AMD), не через «драйвер-паки». Чистая установка раз в полгода.</p>

<h2>7. Проверка диска</h2>
<pre>chkdsk C: /scan</pre>
<p>Если диск HDD — замена на SSD даёт больше, чем всё остальное вместе.</p>

<h2>8. Температуры</h2>
<p>HWiNFO или MSI Afterburner: ЦП выше 90 °C под нагрузкой — чистим кулер и меняем термопасту.</p>

<h2>9. Оперативная память</h2>
<p>8 ГБ в 2025 году мало: браузер + игра съедают всё. 16 ГБ — минимум для комфорта.</p>

<h2>10. Что не помогает</h2>
<ul><li>«Ускорители» и «чистильщики реестра» — вредят.</li>
<li>Отключение файла подкачки — вызывает фризы.</li>
<li>Скачивание «оптимизированных» сборок Windows — риск вирусов.</li></ul>

<h2>Быстрый чек-лист</h2>
<ul><li>Автозагрузка почищена</li><li>Диск заполнен меньше 85%</li>
<li>Драйвер GPU свежий</li><li>Температуры в норме</li><li>Питание на «Высокая производительность»</li></ul>
</body></html>
"""


def guides_pack() -> Path:
    root = folder("guides")
    (root / "guide_obs.html").write_text(GUIDE_OBS, encoding="utf-8")
    (root / "guide_pc.html").write_text(GUIDE_PC, encoding="utf-8")
    (root / "README.txt").write_text(
        "Два гайда (HTML, открываются в браузере):\n"
        "guide_obs.html — OBS с нуля за 20 минут\n"
        "guide_pc.html — ПК без тормозов\n", encoding="utf-8")
    return zip_dir(root, "guides")


def main() -> None:
    tasks = [
        ("alerts_neon", lambda: alerts_pack("alerts_neon", "neon")),
        ("alerts_min", lambda: alerts_pack("alerts_min", "min")),
        ("screens_cyber", screens_pack),
        ("panels_dark", panels_pack),
        ("covers_yt", covers_gradient),
        ("avatars", avatars_pack),
        ("sounds", sounds_pack),
        ("guides", guides_pack),
    ]
    for name, fn in tasks:
        path = fn()
        print(f"{name:14} {path.stat().st_size // 1024:>5} КБ")


if __name__ == "__main__":
    main()
