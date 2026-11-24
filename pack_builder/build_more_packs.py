"""Сборка дополнительных паков: Twitch, обложки, аим-тренажёр.

Запуск: python build_more_packs.py
Результат: assets/packs/{twitch,covers,aim} и zip-архивы рядом в assets/
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from build_pack import (PURPLE, CYAN, alert_gif, font, gradient, mix, save_gif, tone,
                        write_wav)

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
PACKS = ASSETS / "packs"


def folder(name: str) -> Path:
    path = PACKS / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def zip_pack(folder_path: Path, name: str) -> Path:
    out = ASSETS / f"{name}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in folder_path.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(folder_path.parent))
    return out


# ---------------------------------------------------------------- Twitch
PANELS = [
    ("О СТРИМЕ", "кто я и о чём канал", (124, 92, 255)),
    ("ДОНАТ", "поддержать стрим", (58, 215, 255)),
    ("РАСПИСАНИЕ", "когда выхожу в эфир", (255, 92, 160)),
    ("СОЦСЕТИ", "tg · youtube · discord", (120, 200, 120)),
    ("ПРАВИЛА", "уважаем друг друга", (255, 178, 60)),
    ("ЖЕЛЕЗО", "мой сетап", (150, 150, 255)),
]


def panel(title: str, subtitle: str, accent) -> Image.Image:
    w, h = 320, 100
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=16, fill=(14, 16, 28, 235),
                        outline=accent + (200,), width=2)
    d.rounded_rectangle([0, 0, 10, h - 1], radius=6, fill=accent + (255,))
    d.ellipse([26, 30, 66, 70], outline=accent + (255,), width=3)
    d.text((88, 26), title, font=font("C:/Windows/Fonts/segoeuib.ttf", 19),
           fill=(255, 255, 255))
    d.text((88, 56), subtitle, font=font("C:/Windows/Fonts/segoeui.ttf", 13),
           fill=(150, 158, 200))
    return img


def offline_screen() -> Image.Image:
    img = gradient((1920, 1080), (12, 10, 24), (40, 20, 80)).convert("RGBA")
    glow = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([1100, -200, 2100, 700], fill=(124, 92, 255, 190))
    gd.ellipse([-300, 700, 700, 1500], fill=(58, 215, 255, 130))
    glow = glow.filter(ImageFilter.GaussianBlur(130))
    img = Image.alpha_composite(img, glow)

    d = ImageDraw.Draw(img)
    title = "СТРИМ ОФФЛАЙН"
    tw = d.textlength(title, font=font("C:/Windows/Fonts/segoeuib.ttf", 110))
    d.text(((1920 - tw) / 2, 430), title, font=font("C:/Windows/Fonts/segoeuib.ttf", 110),
           fill=(255, 255, 255))
    sub = "следующий эфир — сегодня в 19:00"
    sw = d.textlength(sub, font=font("C:/Windows/Fonts/segoeui.ttf", 38))
    d.text(((1920 - sw) / 2, 590), sub, font=font("C:/Windows/Fonts/segoeui.ttf", 38),
           fill=(180, 190, 240))
    d.rounded_rectangle([(1920 - 260) / 2, 680, (1920 + 260) / 2, 700], radius=10,
                        fill=(58, 215, 255, 220))
    return img.convert("RGB")


TWITCH_GUIDE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Twitch-пак</title><style>
body{background:#0f1118;color:#e8ecff;font-family:Segoe UI,Arial,sans-serif;max-width:820px;margin:40px auto;padding:0 24px;line-height:1.6}
h1{font-size:32px}h2{color:#3ad7ff;margin-top:30px}code{background:#1b2030;padding:2px 6px;border-radius:6px}
.tag{background:#7c5cff;padding:4px 10px;border-radius:999px;font-size:13px}
</style></head><body>
<span class="tag">Frolik Shop</span>
<h1>Twitch-пак</h1>
<p>Оформление канала: алерты, панели, оффлайн-экран и звуки.</p>
<h2>Панели</h2>
<ul><li>Twitch → канал → «Изменить панели» → добавить изображение.</li>
<li>Загрузите файлы из <code>panels/</code> (320×100, уже с рамкой).</li></ul>
<h2>Алерты</h2>
<ul><li>Streamlabs / OBS: источник «Медиа» → <code>alerts/*.gif</code> → «Зацикливание» выкл.</li>
<li>Звук события — из <code>sounds/</code>.</li></ul>
<h2>Оффлайн-экран</h2>
<ul><li>Twitch → Настройки → Канал → «Экран офлайн» → <code>offline.png</code>.</li></ul>
</body></html>
"""


def build_twitch() -> Path:
    root = folder("twitch")
    for sub in ("alerts", "panels", "sounds"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    save_gif(alert_gif("НОВЫЙ ПОДПИСЧИК", "спасибо за поддержку!", PURPLE),
             root / "alerts/follow.gif")
    save_gif(alert_gif("ДОНАТ", "спасибо за донат!", CYAN), root / "alerts/donate.gif")
    save_gif(alert_gif("ПОДПИСКА", "добро пожаловать в клуб!", (255, 92, 160)),
             root / "alerts/sub.gif")
    save_gif(alert_gif("РЕЙД", "к нам пришли зрители!", (255, 178, 60)),
             root / "alerts/raid.gif")

    for i, (title, sub, color) in enumerate(PANELS):
        panel(title, sub, color).save(root / f"panels/panel_{i + 1}.png")

    offline_screen().save(root / "offline.png")

    write_wav(root / "sounds/follow.wav", mix(tone(880, 0.16), [0] * 6000 + tone(1320, 0.22)))
    write_wav(root / "sounds/donate.wav",
              mix(tone(520, 0.12, sweep_to=1040), [0] * 4000 + tone(1560, 0.3)))
    write_wav(root / "sounds/sub.wav", tone(660, 0.2, sweep_to=990))
    write_wav(root / "sounds/raid.wav", tone(330, 0.35, sweep_to=660))

    (root / "guide.html").write_text(TWITCH_GUIDE, encoding="utf-8")
    (root / "README.txt").write_text(
        "Twitch-пак\npanels/ — панели канала\n"
        "alerts/ — GIF-алерты\nsounds/ — звуки\n"
        "offline.png — экран оффлайн\nguide.html — инструкция\n", encoding="utf-8")
    return zip_pack(root, "twitch_pack")


# ---------------------------------------------------------------- обложки
STYLES = [
    ((18, 14, 32), (86, 42, 160), (124, 92, 255)),
    ((10, 22, 32), (16, 80, 110), (58, 215, 255)),
    ((30, 12, 22), (120, 30, 70), (255, 92, 160)),
    ((14, 20, 14), (30, 80, 50), (90, 220, 140)),
]


def cover(size: tuple[int, int], style: int, index: int, with_text: bool) -> Image.Image:
    top, bottom, accent = STYLES[style % len(STYLES)]
    w, h = size
    img = gradient(size, top, bottom).convert("RGBA")

    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([w * 0.55, -h * 0.3, w * 1.4, h * 0.9], fill=accent + (150,))
    gd.ellipse([-w * 0.2, h * 0.45, w * 0.55, h * 1.3], fill=(255, 255, 255, 40))
    glow = glow.filter(ImageFilter.GaussianBlur(int(w * 0.06)))
    img = Image.alpha_composite(img, glow)

    d = ImageDraw.Draw(img)
    # диагональные линии для «движения»
    for k in range(5):
        offset = w * 0.1 + k * w * 0.09
        d.line([(offset, h), (offset + w * 0.25, 0)], fill=(255, 255, 255, 12), width=3)
    d.rectangle([0, h - 12, w, h], fill=accent + (255,))

    if with_text:
        title_font = font("C:/Windows/Fonts/segoeuib.ttf", int(h * 0.13))
        d.text((int(w * 0.06), int(h * 0.55)), "ЗАГОЛОВОК", font=title_font,
               fill=(255, 255, 255))
        d.text((int(w * 0.06), int(h * 0.72)), "подзаголовок · часть 1",
               font=font("C:/Windows/Fonts/segoeui.ttf", int(h * 0.055)),
               fill=(220, 225, 255))
    return img.convert("RGB")


COVERS_GUIDE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Фоны для обложек</title><style>
body{background:#0f1118;color:#e8ecff;font-family:Segoe UI,Arial,sans-serif;max-width:820px;margin:40px auto;padding:0 24px;line-height:1.6}
h1{font-size:32px}h2{color:#3ad7ff;margin-top:30px}code{background:#1b2030;padding:2px 6px;border-radius:6px}
.tag{background:#7c5cff;padding:4px 10px;border-radius:999px;font-size:13px}
</style></head><body>
<span class="tag">Frolik Shop</span>
<h1>Фоны для обложек</h1>
<p>12 фонов 1280×720 и 6 вертикальных 1080×1920. Текста на фонах нет —
пишите свой в любом редакторе.</p>
<h2>Как использовать</h2>
<ul>
<li>Откройте фон в Canva, Photoshop, Figma или даже Paint.</li>
<li>Добавьте заголовок крупным шрифтом (рекомендую 90–120 px для 1280×720).</li>
<li>Экспортируйте в JPG — YouTube принимает до 2 МБ.</li>
</ul>
<h2>Правила читаемости</h2>
<ul>
<li>Держите текст в левой или правой трети — не в центре.</li>
<li>Контраст: светлый текст на тёмной части фона.</li>
<li>Не больше 5–6 слов в заголовке.</li>
</ul>
</body></html>
"""


def build_covers() -> Path:
    root = folder("covers")
    for sub in ("covers_1280x720", "shorts_1080x1920"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    for i in range(12):
        cover((1280, 720), i // 3, i, with_text=False).save(
            root / f"covers_1280x720/cover_{i + 1:02d}.jpg", quality=92)
    for i in range(6):
        cover((1080, 1920), i, i, with_text=False).save(
            root / f"shorts_1080x1920/short_{i + 1:02d}.jpg", quality=92)
    # два примера с текстом
    cover((1280, 720), 0, 0, with_text=True).save(root / "example_with_text.jpg", quality=92)
    (root / "guide.html").write_text(COVERS_GUIDE, encoding="utf-8")
    (root / "README.txt").write_text(
        "Фоны для обложек\n12 горизонтальных + 6 вертикальных\n"
        "example_with_text.jpg — пример с текстом\nguide.html — инструкция\n",
        encoding="utf-8")
    return zip_pack(root, "covers_pack")


# ---------------------------------------------------------------- аим-тренажёр
AIM_GAME = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Аим-тренажёр</title>
<style>
  :root{--bg:#0b0d16;--panel:#141827;--accent:#7c5cff;--cyan:#3ad7ff;--text:#eef1ff}
  *{box-sizing:border-box}
  body{margin:0;background:radial-gradient(circle at 30% 0%,#1b1440,#0b0d16 60%);
       color:var(--text);font-family:Segoe UI,Arial,sans-serif;display:flex;
       flex-direction:column;align-items:center;min-height:100vh}
  header{display:flex;gap:18px;align-items:center;padding:16px;flex-wrap:wrap;justify-content:center}
  h1{font-size:20px;margin:0;letter-spacing:1px}
  .stat{background:var(--panel);border:1px solid #2a3050;border-radius:12px;padding:8px 14px;font-variant-numeric:tabular-nums}
  .stat b{color:var(--cyan)}
  canvas{background:#0e1220;border:2px solid #2a3050;border-radius:18px;cursor:crosshair;
         box-shadow:0 20px 60px rgba(0,0,0,.5)}
  .row{display:flex;gap:10px;padding:14px;flex-wrap:wrap;justify-content:center}
  button{background:var(--panel);color:var(--text);border:1px solid #2a3050;border-radius:10px;
         padding:10px 16px;font-size:14px;cursor:pointer}
  button.active{background:var(--accent);border-color:var(--accent)}
  .hint{color:#7d86a8;font-size:13px;padding-bottom:18px}
</style></head><body>
<header>
  <h1>АИМ-ТРЕНАЖЁР</h1>
  <div class="stat">Счёт: <b id="score">0</b></div>
  <div class="stat">Точность: <b id="acc">100%</b></div>
  <div class="stat">Время: <b id="time">60</b></div>
  <div class="stat">Рекорд: <b id="best">0</b></div>
</header>
<canvas id="c" width="900" height="560"></canvas>
<div class="row">
  <button id="modeFlick" class="active">Флики</button>
  <button id="modeTrack">Трекинг</button>
  <button id="start">Старт / Заново</button>
</div>
<div class="hint">Флики: кликай по мишеням. Трекинг: держи курсор на движущейся цели.</div>
<script>
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const scoreEl = document.getElementById('score'), accEl = document.getElementById('acc');
const timeEl = document.getElementById('time'), bestEl = document.getElementById('best');
let mode = 'flick', running = false, score = 0, shots = 0, hits = 0;
let timeLeft = 60, target = null, trackTime = 0, last = 0, raf = null;
let best = +(localStorage.getItem('aim_best') || 0);
bestEl.textContent = best;

function spawn() {
  const r = 26 + Math.random() * 14;
  target = { x: r + Math.random() * (cv.width - r * 2),
             y: r + Math.random() * (cv.height - r * 2), r, vx: 0, vy: 0 };
  if (mode === 'track') {
    const speed = 180 + Math.random() * 120;
    const a = Math.random() * Math.PI * 2;
    target.vx = Math.cos(a) * speed; target.vy = Math.sin(a) * speed;
  }
}
function reset() {
  score = 0; shots = 0; hits = 0; timeLeft = 60; trackTime = 0;
  scoreEl.textContent = 0; accEl.textContent = '100%'; timeEl.textContent = 60;
  spawn();
}
function draw(dt) {
  ctx.clearRect(0, 0, cv.width, cv.height);
  // сетка
  ctx.strokeStyle = 'rgba(255,255,255,.04)'; ctx.lineWidth = 1;
  for (let x = 0; x < cv.width; x += 60) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, cv.height); ctx.stroke(); }
  for (let y = 0; y < cv.height; y += 60) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(cv.width, y); ctx.stroke(); }

  if (target) {
    if (mode === 'track' && running) {
      target.x += target.vx * dt; target.y += target.vy * dt;
      if (target.x < target.r || target.x > cv.width - target.r) target.vx *= -1;
      if (target.y < target.r || target.y > cv.height - target.r) target.vy *= -1;
    }
    const g = ctx.createRadialGradient(target.x, target.y, 2, target.x, target.y, target.r);
    g.addColorStop(0, '#ffffff'); g.addColorStop(.35, '#3ad7ff'); g.addColorStop(1, 'rgba(58,215,255,.15)');
    ctx.beginPath(); ctx.arc(target.x, target.y, target.r, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill();
    ctx.beginPath(); ctx.arc(target.x, target.y, target.r * .45, 0, Math.PI * 2);
    ctx.fillStyle = '#0b0d16'; ctx.fill();
  }
}
function loop(ts) {
  const dt = Math.min(0.05, (ts - last) / 1000 || 0); last = ts;
  if (running) {
    timeLeft -= dt;
    if (timeLeft <= 0) { timeLeft = 0; stop(); }
    timeEl.textContent = Math.ceil(timeLeft);
    if (mode === 'track' && hoverTarget) trackTime += dt;
  }
  draw(dt);
  raf = requestAnimationFrame(loop);
}
let hoverTarget = false;
cv.addEventListener('mousemove', e => {
  if (!target || mode !== 'track') { hoverTarget = false; return; }
  const r = cv.getBoundingClientRect();
  const x = e.clientX - r.left, y = e.clientY - r.top;
  hoverTarget = Math.hypot(x - target.x, y - target.y) <= target.r;
  if (hoverTarget && running) score += dtScore();
});
function dtScore() { return 0.02; }
cv.addEventListener('mousedown', e => {
  if (!running || mode !== 'flick' || !target) return;
  const r = cv.getBoundingClientRect();
  const x = e.clientX - r.left, y = e.clientY - r.top;
  shots++;
  if (Math.hypot(x - target.x, y - target.y) <= target.r) { hits++; score++; spawn(); }
  accEl.textContent = Math.round(100 * hits / Math.max(1, shots)) + '%';
  scoreEl.textContent = Math.round(score);
});
function start() {
  reset(); running = true;
  if (raf) cancelAnimationFrame(raf);
  last = performance.now(); raf = requestAnimationFrame(loop);
}
function stop() {
  running = false;
  const total = Math.round(score);
  if (total > best) { best = total; localStorage.setItem('aim_best', best); bestEl.textContent = best; }
}
document.getElementById('start').onclick = start;
document.getElementById('modeFlick').onclick = () => { mode = 'flick'; setMode(); };
document.getElementById('modeTrack').onclick = () => { mode = 'track'; setMode(); };
function setMode() {
  document.getElementById('modeFlick').classList.toggle('active', mode === 'flick');
  document.getElementById('modeTrack').classList.toggle('active', mode === 'track');
  reset(); draw(0);
}
setMode();
</script></body></html>
"""

AIM_PLAN = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>План тренировок</title><style>
body{background:#0f1118;color:#e8ecff;font-family:Segoe UI,Arial,sans-serif;max-width:820px;margin:40px auto;padding:0 24px;line-height:1.65}
h1{font-size:32px}h2{color:#3ad7ff;margin-top:28px}li{margin:6px 0}
table{width:100%;border-collapse:collapse;margin-top:12px}
td,th{border-bottom:1px solid #232a44;padding:8px;text-align:left;font-size:15px}
.tag{background:#7c5cff;padding:4px 10px;border-radius:999px;font-size:13px}
</style></head><body>
<span class="tag">Frolik Shop</span>
<h1>14 дней до уверенной стрельбы</h1>
<p>По 15–20 минут в день. Главное — регулярность, а не длительность.</p>

<h2>Как заниматься</h2>
<ul>
<li>Откройте <b>aim/index.html</b> в браузере — это тренажёр.</li>
<li>День 1–3: режим «Флики», 3 подхода по 60 секунд, отдых 30 секунд.</li>
<li>День 4–7: «Флики» + «Трекинг» по 2 подхода.</li>
<li>День 8–14: чередуйте режимы, каждый раз пытайтесь побить рекорд.</li>
</ul>

<h2>Неделя 1</h2>
<table><tr><th>День</th><th>Что делаем</th><th>Цель</th></tr>
<tr><td>1</td><td>Флики, 3×60 с</td><td>почувствовать мышь</td></tr>
<tr><td>2</td><td>Флики, 3×60 с</td><td>+10% к точности</td></tr>
<tr><td>3</td><td>Отдых</td><td>не тренируемся</td></tr>
<tr><td>4</td><td>Трекинг, 3×60 с</td><td>плавность</td></tr>
<tr><td>5</td><td>Флики + трекинг</td><td>переключение</td></tr>
<tr><td>6</td><td>Флики, 4×60 с</td><td>скорость</td></tr>
<tr><td>7</td><td>Отдых</td><td>—</td></tr></table>

<h2>Неделя 2</h2>
<table><tr><th>День</th><th>Что делаем</th><th>Цель</th></tr>
<tr><td>8</td><td>Трекинг, 4×60 с</td><td>удержание</td></tr>
<tr><td>9</td><td>Флики, 4×60 с</td><td>рекорд</td></tr>
<tr><td>10</td><td>Отдых</td><td>—</td></tr>
<tr><td>11</td><td>Флики + трекинг</td><td>стабильность</td></tr>
<tr><td>12</td><td>Флики, 5×60 с</td><td>выносливость</td></tr>
<tr><td>13</td><td>Трекинг, 4×60 с</td><td>точность</td></tr>
<tr><td>14</td><td>Замер рекорда</td><td>сравнить с днём 1</td></tr></table>

<h2>Правила, без которых не работает</h2>
<ul>
<li>Не меняйте чувствительность мыши каждый день — дайте привыкнуть.</li>
<li>Тренируйтесь до игры, а не после: уставшая рука не учится.</li>
<li>Записывайте рекорд — это единственный объективный показатель.</li>
<li>Если болит кисть — стоп. Растяжка важнее рекорда.</li>
</ul>
</body></html>
"""

AIM_GUIDE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Аим-тренажёр</title><style>
body{background:#0f1118;color:#e8ecff;font-family:Segoe UI,Arial,sans-serif;max-width:820px;margin:40px auto;padding:0 24px;line-height:1.6}
h1{font-size:32px}h2{color:#3ad7ff;margin-top:26px}code{background:#1b2030;padding:2px 6px;border-radius:6px}
.tag{background:#7c5cff;padding:4px 10px;border-radius:999px;font-size:13px}
</style></head><body>
<span class="tag">Frolik Shop</span>
<h1>Аим-тренажёр + план</h1>
<ol>
<li>Распакуйте архив.</li>
<li>Откройте <code>aim/index.html</code> двойным кликом — работает офлайн, без установки.</li>
<li>Выберите режим: «Флики» (реакция) или «Трекинг» (плавность).</li>
<li>Нажмите «Старт», тренируйтесь 60 секунд, смотрите счёт и точность.</li>
<li>Откройте <code>plan.html</code> — там 14-дневная программа.</li>
</ol>
<p>Рекорд сохраняется в браузере. Если открываете с другого устройства — рекорд будет свой.</p>
</body></html>
"""


def build_aim() -> Path:
    root = folder("aim")
    (root / "aim").mkdir(parents=True, exist_ok=True)
    (root / "aim/index.html").write_text(AIM_GAME, encoding="utf-8")
    (root / "plan.html").write_text(AIM_PLAN, encoding="utf-8")
    (root / "guide.html").write_text(AIM_GUIDE, encoding="utf-8")
    (root / "README.txt").write_text(
        "Аим-тренажёр\naim/index.html — игра (открыть в браузере)\n"
        "plan.html — план на 14 дней\nguide.html — инструкция\n", encoding="utf-8")
    return zip_pack(root, "aim_pack")


def main() -> None:
    for builder in (build_twitch, build_covers, build_aim):
        path = builder()
        print(f"{path.name}: {path.stat().st_size // 1024} КБ")


if __name__ == "__main__":
    main()
