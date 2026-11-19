"""Draw the Android app's launcher icons from the same mark as the web icons.

    python3 scripts/make_android_icons.py

Writes mobile/android/app/src/main/res/mipmap-*/: the plain and round icons for
older launchers and the layers of the adaptive icon (background, mark, and a
one-colour mark for themed icons). The mark itself lives in make_icons.py;
scripts/build_android.sh runs this on every build.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from make_icons import background, icon, mark

RES = Path(__file__).resolve().parent.parent / "mobile" / "android" / "app" / "src" / "main" / "res"
# density: (launcher icon, adaptive layer) in pixels; a layer is 108 dp, the icon 48 dp
DENSITIES = {"mdpi": (48, 108), "hdpi": (72, 162), "xhdpi": (96, 216), "xxhdpi": (144, 324), "xxxhdpi": (192, 432)}
# A launcher may crop a layer to the middle 66 of its 108 dp, in any shape: keep the mark well inside.
LAYER_REACH = 0.46

ADAPTIVE = """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@mipmap/ic_launcher_background"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
    <monochrome android:drawable="@mipmap/ic_launcher_monochrome"/>
</adaptive-icon>
"""


def one_colour(size: int, reach: float) -> Image.Image:
    """The mark's outline alone, in white: the launcher tints it for themed icons."""
    big = size * 4
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = big / 2
    r = c * reach

    def diamond(scale_x: float, scale_y: float) -> list[tuple[float, float]]:
        return [(c, c - r * scale_y), (c + r * scale_x, c), (c, c + r * scale_y), (c - r * scale_x, c)]

    line = max(2, round(big * 0.03))
    d.polygon(diamond(0.62, 1.0), outline=(255, 255, 255, 255), width=line)
    d.polygon(diamond(0.37, 0.62), outline=(255, 255, 255, 255), width=line)
    dot = r * 0.17
    d.ellipse((c - dot, c - dot, c + dot, c + dot), fill=(255, 255, 255, 255))
    return layer.resize((size, size), Image.LANCZOS)


def round_icon(size: int) -> Image.Image:
    big = size * 4
    base = Image.alpha_composite(background(big).convert("RGBA"), mark(big, 0.50))
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    base.putalpha(mask)
    return base.resize((size, size), Image.LANCZOS)


def main() -> None:
    top = max(layer for _icon, layer in DENSITIES.values())
    top_icon = max(icon_px for icon_px, _layer in DENSITIES.values())
    # draw each once at the largest size, then scale down
    layer_bg = background(top)
    layer_fg = mark(top * 2, LAYER_REACH).resize((top, top), Image.LANCZOS)
    layer_mono = one_colour(top, LAYER_REACH)
    plain = icon(top_icon, False)
    circle = round_icon(top_icon)
    for density, (icon_px, layer_px) in DENSITIES.items():
        folder = RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        plain.resize((icon_px, icon_px), Image.LANCZOS).save(folder / "ic_launcher.png")
        circle.resize((icon_px, icon_px), Image.LANCZOS).save(folder / "ic_launcher_round.png")
        layer_bg.resize((layer_px, layer_px), Image.LANCZOS).save(folder / "ic_launcher_background.png")
        layer_fg.resize((layer_px, layer_px), Image.LANCZOS).save(folder / "ic_launcher_foreground.png")
        layer_mono.resize((layer_px, layer_px), Image.LANCZOS).save(folder / "ic_launcher_monochrome.png")
    anydpi = RES / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True, exist_ok=True)
    (anydpi / "ic_launcher.xml").write_text(ADAPTIVE)
    (anydpi / "ic_launcher_round.xml").write_text(ADAPTIVE)
    print("wrote launcher icons for", ", ".join(DENSITIES))


if __name__ == "__main__":
    main()
