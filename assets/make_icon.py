# -*- coding: utf-8 -*-
"""تولید assets/icon.ico و assets/icon.png — نشان برند ODIN Assistant.

طراحی: مربع گوشه‌گرد تیره (هم‌خانواده با تم شیشه‌ای مونوکروم) + مونوگرام «Ø»
(حلقه + نیزهٔ مورب — اشاره به اودین/اسکاندیناوی) به رنگ سفید. بدون هیچ رنگ
معنایی (سبز/قرمز فقط برای خرید/فروش داخل رابط است، نه لوگو).

اجرا:  python assets/make_icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
S = 1024                      # بوم اصلی (همهٔ اندازه‌ها از این کوچک می‌شوند)
RADIUS = 228
TOP, BOT = (28, 35, 45), (10, 13, 18)          # گرادیان عمودی تیره
INK = (242, 245, 249, 255)                     # سفیدِ نشان


def _gradient() -> Image.Image:
    col = Image.new("RGB", (1, S))
    for y in range(S):
        k = y / (S - 1)
        col.putpixel((0, y), tuple(round(a + (b - a) * k)
                                   for a, b in zip(TOP, BOT)))
    return col.resize((S, S))


def build_master() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1],
                                           radius=RADIUS, fill=255)
    img.paste(_gradient(), (0, 0), mask)

    d = ImageDraw.Draw(img)
    # حاشیهٔ شیشه‌ای ظریف
    d.rounded_rectangle([4, 4, S - 5, S - 5], radius=RADIUS - 4,
                        outline=(255, 255, 255, 34), width=4)

    # مونوگرام Ø : حلقه + نیزهٔ مورب با سرِ گِرد
    cx = cy = S // 2
    ring_r, w = 226, 78
    d.ellipse([cx - ring_r - w // 2, cy - ring_r - w // 2,
               cx + ring_r + w // 2, cy + ring_r + w // 2],
              outline=INK, width=w)
    ext = ring_r + 84
    p1 = (cx - ext * 0.7071, cy + ext * 0.7071)
    p2 = (cx + ext * 0.7071, cy - ext * 0.7071)
    d.line([p1, p2], fill=INK, width=w)
    for px, py in (p1, p2):                    # سرِ گِردِ نیزه
        d.ellipse([px - w / 2, py - w / 2, px + w / 2, py + w / 2], fill=INK)
    return img


def main() -> None:
    master = build_master()
    ico_sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
                 (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(HERE / "icon.ico", format="ICO", sizes=ico_sizes)
    master.resize((512, 512), Image.LANCZOS).save(HERE / "icon.png")
    print(f"[make_icon] icon.ico ({len(ico_sizes)} sizes) + icon.png (512)")


if __name__ == "__main__":
    main()
