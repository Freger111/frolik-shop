"""Сборка рекламного виджета бота: GIF для OBS + HTML для источника «Браузер».

Запуск: python build_bot_ad.py
Результат: assets/obs_bot_ad.gif и assets/widgets/bot_ad.html
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
(ASSETS / "widgets").mkdir(parents=True, exist_ok=True)

W, H = 760, 180
FPS_MS = 50
FRAMES = 48

BOLD = "C:/Windows/Fonts/segoeuib.ttf"
REG = "C:/Windows/Fonts/segoeui.ttf"
PURPLE = (124, 92, 255)
CYAN = (58, 215, 255)


def font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def plate() -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, W - 5, H - 5], radius=30, fill=(14, 16, 28, 242),
                        outline=PURPLE + (220,), width=3)
    d.rounded_rectangle([12, 12, W - 13, H - 13], radius=24,
                        outline=CYAN + (60,), width=1)
    return img


def base_layer() -> Image.Image:
    img = plate()
    d = ImageDraw.Draw(img)

    # логотип
    d.ellipse([28, 52, 104, 128], fill=(24, 18, 46, 255), outline=PURPLE + (255,), width=3)
    f = font(BOLD, 44)
    tw = d.textlength("F", font=f)
    d.text((66 - tw / 2, 58), "F", font=f, fill=(255, 255, 255))

    d.text((124, 36), "FROLIK SHOP", font=font(BOLD, 34), fill=(255, 255, 255))
    d.text((125, 80), "оверлеи · панели · алерты для стрима", font=font(REG, 18),
           fill=(165, 172, 210))
    d.text((125, 112), "t.me/frolikfortnitebot", font=font(BOLD, 24), fill=CYAN)
    return img


def frame(base: Image.Image, i: int) -> Image.Image:
    img = base.copy()

    # блик, бегущий по плашке
    shine = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shine)
    x = -260 + (i / FRAMES) * (W + 520)
    sd.polygon([(x, 0), (x + 90, 0), (x + 30, H), (x - 60, H)], fill=(255, 255, 255, 26))
    shine = shine.filter(ImageFilter.GaussianBlur(10))

    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([4, 4, W - 5, H - 5], radius=30, fill=255)
    img.paste(Image.alpha_composite(img, shine), (0, 0), mask)

    # пульсирующая точка у ссылки
    d = ImageDraw.Draw(img)
    phase = (i / FRAMES) * 2 * 3.14159
    r = 5 + 2.5 * (1 + __import__("math").sin(phase))
    d.ellipse([712 - r, 120 - r, 712 + r, 120 + r], fill=(255, 80, 100, 255))
    return img


HTML = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<style>
  html,body{margin:0;height:100%;background:transparent;overflow:hidden;
            font-family:Segoe UI,Arial,sans-serif}
  .ad{position:absolute;left:0;top:0;display:flex;align-items:center;gap:18px;
      padding:16px 26px 16px 16px;border-radius:28px;background:rgba(14,16,28,.94);
      border:3px solid #7c5cff;box-shadow:0 12px 40px rgba(124,92,255,.35);
      overflow:hidden;white-space:nowrap}
  .ad::after{content:"";position:absolute;top:-40px;left:-140px;width:90px;height:260px;
      background:linear-gradient(90deg,transparent,rgba(255,255,255,.16),transparent);
      transform:rotate(14deg);animation:shine 3.4s linear infinite}
  @keyframes shine{0%{left:-160px}100%{left:120%}}
  .logo{width:76px;height:76px;border-radius:50%;border:3px solid #7c5cff;
        display:flex;align-items:center;justify-content:center;font-weight:800;
        font-size:38px;color:#fff;background:#18122e;flex:none}
  .txt{display:flex;flex-direction:column;gap:2px}
  .name{font-size:30px;font-weight:800;color:#fff;letter-spacing:.5px}
  .sub{font-size:15px;color:#a5acd2}
  .link{font-size:21px;font-weight:800;color:#3ad7ff;margin-top:2px}
  .dot{width:12px;height:12px;border-radius:50%;background:#ff5064;
       animation:pulse 1.4s ease-in-out infinite;flex:none}
  @keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.5);opacity:.6}}
</style></head>
<body>
  <div class="ad">
    <div class="logo">F</div>
    <div class="txt">
      <div class="name">FROLIK SHOP</div>
      <div class="sub">оверлеи · панели · алерты для стрима</div>
      <div class="link">t.me/frolikfortnitebot</div>
    </div>
    <div class="dot"></div>
  </div>
</body></html>
"""


def save_gif(frames: list[Image.Image], out: Path) -> None:
    """Единая палитра на все кадры + прозрачность в один индекс."""
    palette_source = frames[0].convert("RGB").quantize(colors=255, method=Image.MEDIANCUT)
    palette = list(palette_source.getpalette() or [])[:255 * 3]
    palette += [0] * (768 - len(palette))          # 256-й цвет — прозрачный

    converted = []
    for f in frames:
        p = f.convert("RGB").quantize(palette=palette_source, dither=Image.NONE)
        p.putpalette(palette)
        alpha = f.getchannel("A")
        transparent = alpha.point(lambda a: 255 if a < 128 else 0)
        p.paste(255, mask=transparent)
        converted.append(p)
    converted[0].save(out, save_all=True, append_images=converted[1:],
                      duration=FPS_MS, loop=0, transparency=255, disposal=2,
                      optimize=False)


def main() -> None:
    base = base_layer()
    frames = [frame(base, i) for i in range(FRAMES)]
    out = ASSETS / "obs_bot_ad.gif"
    save_gif(frames, out)

    (ASSETS / "widgets" / "bot_ad.html").write_text(HTML, encoding="utf-8")
    print("gif:", round(out.stat().st_size / 1024), "КБ", out)
    print("html:", ASSETS / "widgets" / "bot_ad.html")


if __name__ == "__main__":
    main()
