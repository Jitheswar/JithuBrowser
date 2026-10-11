#!/usr/bin/env python3
"""Render JithuBrowser icons (PNG sizes, Windows .ico, SVG) from one definition."""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "icons")
S = 1024
TOP, BOT = (49, 92, 246), (124, 58, 237)        # blue -> violet


def shield(d, s, inset=0):
    k = s / 1024
    pts = [(512, 96 + inset), (872 - inset, 224 + inset), (872 - inset, 520),
           (832, 700), (700, 860), (512, 944 - inset), (324, 860), (192, 700),
           (152 + inset, 520), (152 + inset, 224 + inset)]
    return [(x * k, y * k) for x, y in pts]


def render():
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / (S - 1)
        gd.line([(0, y), (S, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(TOP, BOT)) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(shield(None, S), fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    w = 92  # stroke of the J
    # J: top serif, stem, and a hook (same geometry as the SVG path)
    h, cx, cy, r = w // 2, 443, 623, 123
    d.line([(486, 346), (644, 346)], fill="white", width=w)
    d.line([(566, 346), (566, cy)], fill="white", width=w)
    d.arc([cx - r - h, cy - r - h, cx + r + h, cy + r + h], start=0, end=180, fill="white", width=w)
    for x, y in [(486, 346), (644, 346), (566, 346), (cx - r, cy)]:
        d.ellipse([x - h, y - h, x + h, y + h], fill="white")
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    big = render()
    for s in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        big.resize((s, s), Image.LANCZOS).save(os.path.join(OUT, f"product_logo_{s}.png"))
    big.save(os.path.join(OUT, "product_logo_1024.png"))
    big.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "jithubrowser.ico"),
                                               sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    pts = " ".join(f"{x:.0f},{y:.0f}" for x, y in shield(None, S))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="rgb{TOP}"/><stop offset="1" stop-color="rgb{BOT}"/></linearGradient></defs>
  <polygon points="{pts}" fill="url(#g)"/>
  <g fill="none" stroke="#fff" stroke-width="92" stroke-linecap="round">
    <path d="M486 346H644M566 346V623A123 123 0 0 1 320 623"/>
  </g>
</svg>
'''
    open(os.path.join(OUT, "jithubrowser.svg"), "w").write(svg)


if __name__ == "__main__":
    main()
