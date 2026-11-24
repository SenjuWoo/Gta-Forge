#!/usr/bin/env python3
"""Render docs/icon.png (512) and docs/icon.svg for the README. Reproducible: python tools/make_icon.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
OUT.mkdir(exist_ok=True)
S = 512


def font(size: int):
    for p in (r"C:\Windows\Fonts\segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# rounded square, vertical gradient purple -> teal
top, bot = (124, 58, 237), (6, 182, 212)
for y in range(S):
    t = y / (S - 1)
    c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
    d.line([(0, y), (S, y)], fill=c + (255,))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=110, fill=255)
img.putalpha(mask)
d = ImageDraw.Draw(img)
# road stripes
for i, x in enumerate((150, 256, 362)):
    d.rounded_rectangle([x - 10, 96, x + 10, 416], radius=10, fill=(255, 255, 255, 46 if i == 1 else 70))
# monogram
f = font(190)
text = "GF"
box = d.textbbox((0, 0), text, font=f)
d.text(((S - (box[2] - box[0])) / 2 - box[0], (S - (box[3] - box[1])) / 2 - box[1] - 8), text, font=f, fill=(255, 255, 255, 255))
# VI badge
f2 = font(44)
b2 = d.textbbox((0, 0), "VI", font=f2)
w2 = b2[2] - b2[0]
d.rounded_rectangle([(S - w2 - 64) / 2, 404, (S + w2 + 64) / 2, 468], radius=32, fill=(9, 9, 11, 255))
d.text(((S - w2) / 2 - b2[0], 412 - b2[1]), "VI", font=f2, fill=(34, 211, 238, 255))
img.save(OUT / "icon.png")

svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="GTA Forge">
  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#7c3aed"/><stop offset="1" stop-color="#06b6d4"/>
  </linearGradient></defs>
  <rect width="512" height="512" rx="110" fill="url(#g)"/>
  <g fill="#fff" opacity=".18"><rect x="140" y="96" width="20" height="320" rx="10"/><rect x="246" y="96" width="20" height="320" rx="10"/><rect x="352" y="96" width="20" height="320" rx="10"/></g>
  <text x="256" y="300" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="190" font-weight="700" fill="#fff">GF</text>
  <rect x="192" y="404" width="128" height="64" rx="32" fill="#09090b"/>
  <text x="256" y="450" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="44" font-weight="700" fill="#22d3ee">VI</text>
</svg>
"""
(OUT / "icon.svg").write_text(svg, encoding="utf-8")
print(OUT / "icon.png", (OUT / "icon.png").stat().st_size)