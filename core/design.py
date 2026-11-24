"""Оформление: обложки товаров, баннер магазина, шаблоны сообщений."""
from __future__ import annotations

import io
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "assets"
ASSETS.mkdir(exist_ok=True)

FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_REG = "C:/Windows/Fonts/segoeui.ttf"

PALETTES = [
    ((124, 92, 255), (58, 215, 255)),
    ((255, 92, 160), (124, 92, 255)),
    ((255, 178, 60), (255, 92, 120)),
    ((60, 200, 140), (58, 215, 255)),
    ((120, 120, 255), (200, 120, 255)),
]


def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _gradient(size: tuple[int, int], colors: tuple) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, colors[0])
    draw = ImageDraw.Draw(img)
    c1, c2 = colors
    for y in range(h):
        t = y / max(1, h - 1)
        color = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)
    return img


def _round_corners(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1],
                                           radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def banner(title: str = "FROLIK SHOP", subtitle: str = "цифровые товары · быстрая выдача") -> bytes:
    """Баннер для приветствия."""
    img = _gradient((1200, 480), ((18, 20, 34), (60, 40, 120)))
    draw = ImageDraw.Draw(img)

    # декоративные круги
    draw.ellipse([820, -120, 1320, 380], fill=(124, 92, 255))
    draw.ellipse([980, 200, 1360, 580], fill=(58, 215, 255))
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([70, 130, 700, 350], radius=36, fill=(12, 14, 24, 190))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(img)
    draw.text((110, 160), title, font=_font(FONT_BOLD, 68), fill=(255, 255, 255))
    draw.text((112, 248), subtitle, font=_font(FONT_REG, 28), fill=(180, 190, 255))
    draw.text((112, 292), "оплата по СБП · выдача сразу", font=_font(FONT_REG, 22),
              fill=(140, 150, 200))

    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=90)
    return out.getvalue()


def cover(title: str, index: int = 0) -> bytes:
    """Обложка товара: градиент + название."""
    colors = PALETTES[index % len(PALETTES)]
    img = _gradient((900, 600), colors)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([50, 380, 850, 560], radius=28, fill=(10, 12, 20, 185))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(img)
    lines = textwrap.wrap(title, width=18)[:3]
    y = 405
    for line in lines:
        draw.text((80, y), line, font=_font(FONT_BOLD, 46), fill=(255, 255, 255))
        y += 52
    draw.text((80, 60), "FROLIK SHOP", font=_font(FONT_BOLD, 26), fill=(255, 255, 255))

    out = io.BytesIO()
    _round_corners(img.convert("RGB"), 24).convert("RGB").save(out, "JPEG", quality=90)
    return out.getvalue()
