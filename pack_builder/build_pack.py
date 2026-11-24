"""Сборка пака «Стрим за 10 минут»: оверлеи, экраны, алерты, звуки, виджеты.

Запуск: python build_pack.py
Результат: папка assets/obs_pack и архив assets/obs_pack.zip
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "assets" / "obs_pack"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_REG = "C:/Windows/Fonts/segoeui.ttf"

PURPLE = (124, 92, 255)
CYAN = (58, 215, 255)
DARK = (12, 14, 24)


def font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def ensure(*parts: str) -> Path:
    path = OUT.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def gradient(size, top, bottom) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        draw.line([(0, y), (w, y)],
                  fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img


def glow_layer(size, draw_fn, blur: int = 24) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    return layer.filter(ImageFilter.GaussianBlur(blur))


# ---------------------------------------------------------------- оверлеи
def frame_full() -> Image.Image:
    w, h = 1920, 1080
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = 34
    d.rounded_rectangle([pad, pad, w - pad, h - pad], radius=30,
                        outline=(124, 92, 255, 190), width=3)
    d.rounded_rectangle([pad + 8, pad + 8, w - pad - 8, h - pad - 8], radius=24,
                        outline=(58, 215, 255, 70), width=1)
    # угловые акценты
    for (x, y, dx, dy) in ((pad, pad, 1, 1), (w - pad, pad, -1, 1),
                           (pad, h - pad, 1, -1), (w - pad, h - pad, -1, -1)):
        d.line([(x, y), (x + dx * 150, y)], fill=(58, 215, 255, 230), width=5)
        d.line([(x, y), (x, y + dy * 150)], fill=(58, 215, 255, 230), width=5)
    return img


def top_bar() -> Image.Image:
    w, h = 1920, 130
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 24, w - 40, h - 20], radius=28, fill=(14, 16, 28, 200))
    d.rounded_rectangle([40, 24, w - 40, h - 20], radius=28,
                        outline=(124, 92, 255, 160), width=2)
    d.rounded_rectangle([40, 24, 330, h - 20], radius=28, fill=(124, 92, 255, 235))
    d.text((72, 44), "НА СВЯЗИ", font=font(FONT_BOLD, 30), fill=(255, 255, 255))
    d.ellipse([352, 56, 372, 76], fill=(255, 80, 100))
    d.text((386, 46), "LIVE", font=font(FONT_BOLD, 26), fill=(255, 255, 255))
    return img


def webcam_frame() -> Image.Image:
    size = 480
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 6, size - 6, size - 6], radius=36,
                        outline=(124, 92, 255, 255), width=6)
    d.rounded_rectangle([22, 22, size - 22, size - 22], radius=26,
                        outline=(58, 215, 255, 90), width=2)
    return img


def lower_third() -> Image.Image:
    w, h = 1200, 200
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 30, w - 40, h - 30], radius=26, fill=(14, 16, 28, 215))
    d.rounded_rectangle([0, 30, 16, h - 30], radius=8, fill=(58, 215, 255, 255))
    d.rounded_rectangle([0, 30, w - 40, h - 30], radius=26,
                        outline=(124, 92, 255, 170), width=2)
    d.text((48, 56), "ИМЯ ИГРОКА", font=font(FONT_BOLD, 40), fill=(255, 255, 255))
    d.text((50, 112), "подпись · роль · соцсеть", font=font(FONT_REG, 24),
           fill=(150, 160, 210))
    return img


def logo_corner() -> Image.Image:
    size = 320
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([10, 10, size - 10, size - 10], fill=(14, 16, 28, 210),
              outline=(124, 92, 255, 230), width=5)
    d.ellipse([34, 34, size - 34, size - 34], outline=(58, 215, 255, 80), width=2)
    d.text((92, 110), "F", font=font(FONT_BOLD, 96), fill=(255, 255, 255))
    d.text((120, 214), "SHOP", font=font(FONT_BOLD, 28), fill=(58, 215, 255))
    return img


# ---------------------------------------------------------------- экраны
def screen(title: str, subtitle: str, footer: str = "") -> Image.Image:
    img = gradient((1920, 1080), (16, 12, 34), (46, 24, 92)).convert("RGBA")
    glow = glow_layer((1920, 1080), lambda d: (
        d.ellipse([1200, -200, 2100, 700], fill=(124, 92, 255, 200)),
        d.ellipse([-200, 600, 700, 1400], fill=(58, 215, 255, 140)),
    ), blur=120)
    img = Image.alpha_composite(img, glow)

    d = ImageDraw.Draw(img)
    tw = d.textlength(title, font=font(FONT_BOLD, 130))
    d.text(((1920 - tw) / 2, 420), title, font=font(FONT_BOLD, 130), fill=(255, 255, 255))
    sw = d.textlength(subtitle, font=font(FONT_REG, 40))
    d.text(((1920 - sw) / 2, 590), subtitle, font=font(FONT_REG, 40), fill=(180, 190, 240))
    d.rounded_rectangle([(1920 - 260) / 2, 700, (1920 + 260) / 2, 716], radius=8,
                        fill=(58, 215, 255, 220))
    if footer:
        fw = d.textlength(footer, font=font(FONT_REG, 28))
        d.text(((1920 - fw) / 2, 960), footer, font=font(FONT_REG, 28), fill=(120, 130, 180))
    return img.convert("RGB")


# ---------------------------------------------------------------- алерты (GIF)
def alert_gif(title: str, subtitle: str, accent) -> list[Image.Image]:
    frames = []
    w, h = 640, 320
    for i in range(12):
        t = i / 11
        scale = 0.85 + 0.15 * min(1, t * 3)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        pad_x = int(20 + (1 - scale) * 120)
        box = [pad_x, int(30 + (1 - scale) * 40), w - pad_x, h - int(30 + (1 - scale) * 40)]
        d.rounded_rectangle(box, radius=28, fill=(14, 16, 28, 235),
                            outline=accent + (255,), width=3)
        d.rounded_rectangle([box[0], box[1], box[0] + 12, box[3]], radius=6, fill=accent + (255,))
        d.text((box[0] + 40, box[1] + 44), title, font=font(FONT_BOLD, 40), fill=(255, 255, 255))
        d.text((box[0] + 42, box[1] + 110), subtitle, font=font(FONT_REG, 26),
               fill=(170, 180, 230))
        # блик
        shift = -200 + i * 90
        d.rounded_rectangle([shift, box[1], shift + 90, box[3]], radius=20,
                            fill=(255, 255, 255, 18))
        frames.append(img.convert("RGBA"))
    return frames


def save_gif(frames: list[Image.Image], path: Path, duration: int = 60) -> None:
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=duration,
                   loop=0, disposal=2)


# ---------------------------------------------------------------- звуки
def tone(freq: float, dur: float, rate: int = 44100, vol: float = 0.35,
         sweep_to: float | None = None) -> list[float]:
    count = int(rate * dur)
    out = []
    phase = 0.0
    for i in range(count):
        f = freq if sweep_to is None else freq + (sweep_to - freq) * (i / count)
        phase += 2 * math.pi * f / rate
        env = min(1.0, i / (rate * 0.01), (count - i) / (rate * 0.05))
        out.append(math.sin(phase) * vol * env)
    return out


def mix(*tracks: list[float]) -> list[float]:
    length = max(len(t) for t in tracks)
    out = [0.0] * length
    for track in tracks:
        for i, v in enumerate(track):
            out[i] += v
    return out


def write_wav(path: Path, samples: list[float], rate: int = 44100) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767))
                               for s in samples))


# ---------------------------------------------------------------- виджет
WIDGET = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>Скоро начнём</title>
<style>
  html,body{margin:0;height:100%;background:transparent;font-family:Segoe UI,Arial,sans-serif;overflow:hidden}
  .wrap{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
  .card{padding:48px 64px;border-radius:32px;background:rgba(14,16,28,.88);
        border:2px solid rgba(124,92,255,.85);text-align:center;color:#fff;
        box-shadow:0 0 60px rgba(124,92,255,.45)}
  h1{margin:0 0 10px;font-size:56px;letter-spacing:2px}
  p{margin:0;color:#aab3e0;font-size:22px}
  .timer{margin-top:26px;font-size:64px;font-weight:700;color:#3ad7ff;font-variant-numeric:tabular-nums}
  .bar{height:8px;border-radius:8px;margin-top:26px;background:rgba(255,255,255,.12);overflow:hidden}
  .fill{height:100%;width:30%;background:linear-gradient(90deg,#7c5cff,#3ad7ff);animation:slide 2.4s infinite}
  @keyframes slide{0%{transform:translateX(-100%)}100%{transform:translateX(340%)}}
</style></head>
<body><div class="wrap"><div class="card">
  <h1>СКОРО НАЧНЁМ</h1>
  <p>настройка сцены · проверка звука</p>
  <div class="timer" id="t">05:00</div>
  <div class="bar"><div class="fill"></div></div>
</div></div>
<script>
let left = 300;
setInterval(() => {
  left = Math.max(0, left - 1);
  const m = String(Math.floor(left / 60)).padStart(2, '0');
  const s = String(left % 60).padStart(2, '0');
  document.getElementById('t').textContent = m + ':' + s;
}, 1000);
</script></body></html>
"""

GUIDE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Пак «Стрим за 10 минут»</title>
<style>
 body{background:#0f1118;color:#e8ecff;font-family:Segoe UI,Arial,sans-serif;
      max-width:820px;margin:40px auto;padding:0 24px;line-height:1.6}
 h1{font-size:34px;margin-bottom:6px}
 h2{margin-top:34px;color:#3ad7ff;font-size:22px}
 code{background:#1b2030;padding:2px 6px;border-radius:6px}
 li{margin:6px 0}
 .tag{display:inline-block;background:#7c5cff;padding:4px 10px;border-radius:999px;font-size:13px}
</style></head><body>
<span class="tag">Frolik Shop</span>
<h1>Стрим за 10 минут</h1>
<p>Пак оверлеев, экранов и звуков для OBS. Ниже — короткая инструкция.</p>

<h2>1. Добавляем оверлей</h2>
<ul>
  <li>В OBS: <code>Источники → + → Изображение</code>.</li>
  <li>Выберите файл из папки <code>overlays/</code>, например <code>frame_full.png</code>.</li>
  <li>Растяните на весь экран (правый клик → «Вписать в экран»).</li>
  <li>То же для <code>top_bar.png</code>, <code>lower_third.png</code>, <code>logo_corner.png</code>.</li>
</ul>

<h2>2. Вебкамера</h2>
<ul>
  <li>Источник <code>Устройство захвата видео</code> → ваша камера.</li>
  <li>Поверх него положите <code>overlays/webcam_frame.png</code> и подгоните под размер камеры.</li>
</ul>

<h2>3. Экраны пауз</h2>
<ul>
  <li><code>screens/starting_soon.png</code> — до начала стрима.</li>
  <li><code>screens/brb.png</code> — отошли.</li>
  <li><code>screens/ending.png</code> — завершение.</li>
  <li>Живой таймер: добавьте источник <code>Браузер</code> и укажите файл <code>widgets/starting_soon.html</code>.</li>
</ul>

<h2>4. Алерты</h2>
<ul>
  <li>Готовые GIF: <code>alerts/follow.gif</code>, <code>alerts/donate.gif</code>.</li>
  <li>В OBS: источник «Медиа» → файл GIF → «Зациклить» выключить.</li>
  <li>Звуки: <code>sounds/follow.wav</code>, <code>donate.wav</code>, <code>alert.wav</code>.</li>
</ul>

<h2>5. Цвета</h2>
<p>Основные цвета пака: <code>#7c5cff</code> (фиолетовый) и <code>#3ad7ff</code> (циан) —
их же можно поставить в теме OBS, чтобы всё смотрелось единым.</p>

<h2>Лицензия</h2>
<p>Используйте на своих стримах без ограничений. Перепродавать сам пак нельзя.</p>
</body></html>
"""


def main() -> None:
    for folder in ("overlays", "screens", "alerts", "sounds", "widgets"):
        ensure(folder)

    frame_full().save(OUT / "overlays/frame_full.png")
    top_bar().save(OUT / "overlays/top_bar.png")
    webcam_frame().save(OUT / "overlays/webcam_frame.png")
    lower_third().save(OUT / "overlays/lower_third.png")
    logo_corner().save(OUT / "overlays/logo_corner.png")

    screen("СКОРО НАЧНЁМ", "настройка сцены · проверка звука",
           "спасибо, что зашли").save(OUT / "screens/starting_soon.png")
    screen("ОТОШЁЛ", "вернусь через пару минут", "не уходите").save(OUT / "screens/brb.png")
    screen("СТРИМ ЗАВЕРШЁН", "спасибо за вечер", "до следующего раза").save(
        OUT / "screens/ending.png")

    save_gif(alert_gif("НОВЫЙ ПОДПИСЧИК", "спасибо за поддержку!", PURPLE),
             OUT / "alerts/follow.gif")
    save_gif(alert_gif("ДОНАТ", "спасибо за донат!", CYAN), OUT / "alerts/donate.gif")

    write_wav(OUT / "sounds/follow.wav",
              mix(tone(880, 0.16), [0] * 6000 + tone(1320, 0.22)))
    write_wav(OUT / "sounds/donate.wav",
              mix(tone(520, 0.12, sweep_to=1040), [0] * 4000 + tone(1560, 0.3)))
    write_wav(OUT / "sounds/alert.wav", tone(660, 0.28, sweep_to=990))
    write_wav(OUT / "sounds/click.wav", tone(1200, 0.04, vol=0.2))

    (OUT / "widgets/starting_soon.html").write_text(WIDGET, encoding="utf-8")
    (OUT / "guide.html").write_text(GUIDE, encoding="utf-8")
    (OUT / "README.txt").write_text(
        "Пак «Стрим за 10 минут»\n"
        "overlays/ — рамки и плашки для OBS\n"
        "screens/  — экраны пауз\n"
        "alerts/   — GIF-алерты\n"
        "sounds/   — звуки событий\n"
        "widgets/  — живой таймер для источника «Браузер»\n"
        "guide.html — инструкция\n", encoding="utf-8")

    print("Собрано:", sum(1 for _ in OUT.rglob("*") if _.is_file()), "файлов")


if __name__ == "__main__":
    main()
