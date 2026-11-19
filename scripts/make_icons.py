"""Draw the app icons (the card-back mark: a lantern diamond on night blue).

    python3 scripts/make_icons.py

Writes frontend/public/icons/*.png and frontend/public/favicon.svg. Re-run after changing the mark.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public"
NIGHT_TOP = (35, 42, 65)
NIGHT_BOTTOM = (11, 13, 22)
AMBER = (244, 181, 69)
GLOW = (255, 214, 130)


def background(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = min(1.0, (x * 0.35 + y * 0.9) / (size * 1.1))
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(NIGHT_TOP, NIGHT_BOTTOM))
    return img


def mark(size: int, reach: float) -> Image.Image:
    """The diamond, drawn so it stays inside `reach` (share of the half-size) of the centre."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = size / 2
    r = c * reach

    def diamond(scale_x: float, scale_y: float) -> list[tuple[float, float]]:
        return [(c, c - r * scale_y), (c + r * scale_x, c), (c, c + r * scale_y), (c - r * scale_x, c)]

    line = max(2, round(size * 0.022))
    d.polygon(diamond(0.62, 1.0), outline=AMBER + (190,), width=line)
    d.polygon(diamond(0.37, 0.62), fill=AMBER + (46,), outline=AMBER + (235,), width=line)
    dot = r * 0.15
    d.ellipse((c - dot, c - dot, c + dot, c + dot), fill=GLOW + (255,))

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    halo = r * 0.5
    g.ellipse((c - halo, c - halo, c + halo, c + halo), fill=AMBER + (120,))
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.06))
    return Image.alpha_composite(glow, layer)


def icon(size: int, maskable: bool) -> Image.Image:
    big = size * 4
    base = background(big).convert("RGBA")
    # A maskable icon may be cropped to a circle: keep the mark inside the middle 80 %.
    base = Image.alpha_composite(base, mark(big, 0.50 if maskable else 0.66))
    if not maskable:
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=round(big * 0.22), fill=255)
        base.putalpha(mask)
    return base.resize((size, size), Image.LANCZOS)


def main() -> None:
    icons = OUT / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    icon(192, False).save(icons / "icon-192.png")
    icon(512, False).save(icons / "icon-512.png")
    icon(512, True).convert("RGB").save(icons / "maskable-512.png")
    icon(180, True).convert("RGB").save(icons / "apple-touch-icon.png")
    (OUT / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<defs><linearGradient id="n" x1="0" y1="0" x2=".4" y2="1">'
        '<stop offset="0" stop-color="#232a41"/><stop offset="1" stop-color="#0b0d16"/></linearGradient></defs>'
        '<rect width="64" height="64" rx="14" fill="url(#n)"/>'
        '<path d="M32 11 45 32 32 53 19 32Z" fill="none" stroke="#f4b545" stroke-width="2" opacity=".75"/>'
        '<path d="M32 19 40 32 32 45 24 32Z" fill="#f4b545" fill-opacity=".2" stroke="#f4b545" stroke-width="2"/>'
        '<circle cx="32" cy="32" r="3.4" fill="#ffd682"/></svg>\n'
    )
    print("wrote", ", ".join(sorted(p.name for p in icons.iterdir())), "and favicon.svg")


if __name__ == "__main__":
    main()
