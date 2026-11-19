#!/usr/bin/env python3
"""Make the pictures for the rewards: card backs, tables, rank badges and the pack lantern.

    OPENROUTER_API_KEY=... python3 scripts/generate_cosmetics.py --raw <folder> [names...]
    python3 scripts/generate_cosmetics.py --raw <folder> --pack-only

Two steps, kept apart so a picture can be redone without paying for the rest again:

  1. ask an image model (OpenRouter's image endpoint) for each picture and keep what comes back,
     untouched, in the raw folder. A picture already there is not asked for again;
  2. cut each raw picture to the shape the game uses and write it as WebP into
     frontend/src/progress/art/, from where the build ships it with the game.

Every prompt is a plain description of an original picture. The key is read from the
environment and is never printed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "src" / "progress" / "art"
ENDPOINT = "https://openrouter.ai/api/v1/images"
MODEL = os.environ.get("COSMETICS_MODEL", "recraft/recraft-v4.1-flash-v2:free")

BACK_STYLE = (
    "Ornamental playing card back design, perfectly symmetrical, flat vector illustration with fine "
    "line work, one centred emblem inside a decorative border that runs along all four edges, "
    "the design fills the whole image edge to edge, no text, no letters, no numbers, no watermark. "
)
TABLE_STYLE = (
    "Flat material texture photographed straight from above, orthographic, evenly lit with no "
    "hotspot and no vignette, the material fills the entire frame edge to edge, no perspective, "
    "no horizon, no table edge, no objects, no text. Dark, muted, low contrast. Material: "
)
BADGE_STYLE = (
    "A single round enamel badge seen straight on, centred, filling the image, thick polished rim, "
    "flat vector emblem with clean shapes, plain pure black background outside the badge, "
    "no text, no letters, no numbers. "
)

# name: (kind, aspect ratio, prompt)
PICTURES: dict[str, tuple[str, str, str]] = {
    # ---- card backs -------------------------------------------------------------------------
    "back_ember": ("back", "3:4", BACK_STYLE + "Emblem: a glowing ember inside a woven lattice. Deep charcoal and burnt orange with thin gold lines."),
    "back_moth": ("back", "3:4", BACK_STYLE + "Emblem: a moth with spread patterned wings. Dusty violet, cream and silver on dark plum."),
    "back_tide": ("back", "3:4", BACK_STYLE + "Emblem: a curling wave under a small crescent moon. Teal, sea green and pearl white on deep navy."),
    "back_moss": ("back", "3:4", BACK_STYLE + "Emblem: a fern frond coiled around a brass ring. Moss green and aged brass on dark forest green."),
    "back_frost": ("back", "3:4", BACK_STYLE + "Emblem: a six-pointed ice crystal made of thin glass facets. Pale icy blue and white on slate blue."),
    "back_bloom": ("back", "3:4", BACK_STYLE + "Emblem: a night-blooming flower with layered petals. Magenta, rose and gold on near-black indigo."),
    "back_crane": ("back", "3:4", BACK_STYLE + "Emblem: a folded paper crane in flight. Warm paper white and vermilion red on dark teal."),
    "back_chart": ("back", "3:4", BACK_STYLE + "Emblem: a star chart with a compass rose and dotted constellations. Midnight blue with fine gold lines."),
    "back_coil": ("back", "3:4", BACK_STYLE + "Emblem: interlocking copper gears around a small flame. Copper, bronze and soot black."),
    "back_ink": ("back", "3:4", BACK_STYLE + "Emblem: a quill pen crossing an inkwell, with ink flourishes. Black ink and sepia on aged parchment."),
    "back_dawn": ("back", "3:4", BACK_STYLE + "Emblem: a rising sun with long straight rays over hills. Amber, coral and pale gold on dusky purple."),
    # ---- tables -----------------------------------------------------------------------------
    "table_oak": ("table", "16:9", TABLE_STYLE + "old dark oak planks running left to right, visible grain, oiled and worn."),
    "table_slate": ("table", "16:9", TABLE_STYLE + "dark blue-grey slate stone with faint natural veins."),
    "table_velvet": ("table", "16:9", TABLE_STYLE + "deep burgundy velvet cloth with a soft nap, smooth, no folds."),
    "table_moss": ("table", "16:9", TABLE_STYLE + "flat grey flagstones with dark green moss growing in the gaps between them."),
    "table_sand": ("table", "16:9", TABLE_STYLE + "dark raked sand with long smooth parallel wavy lines."),
    # ---- rank badges ------------------------------------------------------------------------
    "rank_spark": ("badge", "1:1", BADGE_STYLE + "Emblem: one tiny spark with a few short rays. Dull iron rim, dark grey enamel, small orange spark."),
    "rank_wick": ("badge", "1:1", BADGE_STYLE + "Emblem: a short candle wick with a very small flame. Iron rim, dark brown enamel."),
    "rank_candle": ("badge", "1:1", BADGE_STYLE + "Emblem: a lit candle in a small dish. Bronze rim, deep red enamel, warm yellow flame."),
    "rank_lamp": ("badge", "1:1", BADGE_STYLE + "Emblem: a small oil lamp with a round glass chimney. Bronze rim, dark green enamel."),
    "rank_lantern": ("badge", "1:1", BADGE_STYLE + "Emblem: a square hanging lantern with a bright flame inside. Brass rim, deep blue enamel."),
    "rank_beacon": ("badge", "1:1", BADGE_STYLE + "Emblem: a signal fire burning in an iron basket on a hilltop. Silver rim, dark teal enamel, tall orange flames."),
    "rank_lighthouse": ("badge", "1:1", BADGE_STYLE + "Emblem: a lighthouse on a rock sending two beams of light. Silver rim, navy enamel, white beams."),
    "rank_daystar": ("badge", "1:1", BADGE_STYLE + "Emblem: a radiant eight-pointed morning star above a horizon line. Gold rim, royal purple enamel, bright gold star."),
    # ---- the pack ---------------------------------------------------------------------------
    "pack_sealed": ("lantern", "3:4", "A closed paper sky lantern, unlit, tied shut with a thin cord and a small wax seal, tall rounded shape, cream paper with a faint painted pattern, soft studio light, centred, whole lantern visible with space around it, plain pure black background, digital painting, no text."),
}


def ask(prompt: str, aspect: str) -> bytes:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        sys.exit("OPENROUTER_API_KEY is not set")
    body = json.dumps({"model": MODEL, "prompt": prompt, "aspect_ratio": aspect, "n": 1}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            data = json.load(res)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}") from None
    items = data.get("data") or []
    if not items or not items[0].get("b64_json"):
        raise RuntimeError(f"no picture in the answer: {json.dumps(data)[:300]}")
    return base64.b64decode(items[0]["b64_json"])


def crop_to(img: Image.Image, ratio: float) -> Image.Image:
    w, h = img.size
    if w / h > ratio:
        nw = round(h * ratio)
        left = (w - nw) // 2
        return img.crop((left, 0, left + nw, h))
    nh = round(w / ratio)
    top = (h - nh) // 2
    return img.crop((0, top, w, top + nh))


def pack(name: str, kind: str, raw: Path) -> Path:
    img = Image.open(raw).convert("RGB")
    out = OUT / f"{name}.webp"
    if kind == "back":
        img = crop_to(img, 5 / 7).resize((300, 420), Image.LANCZOS)
        img.save(out, "WEBP", quality=80, method=6)
    elif kind == "table":
        # Drawn under the pieces: kept soft and small, the game darkens it further.
        img = crop_to(img, 16 / 9).resize((1280, 720), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
        img.save(out, "WEBP", quality=62, method=6)
    elif kind == "badge":
        # The badge is round on a black ground and not always the same size: find it, cut the
        # picture square around it, and make everything outside the circle see-through.
        lit = img.convert("L").point(lambda v: 255 if v > 34 else 0)
        left, top, right, bottom = lit.getbbox() or (0, 0, *img.size)
        r = round(max(right - left, bottom - top) / 2 * 0.985)
        cx, cy = (left + right) // 2, (top + bottom) // 2
        img = img.crop((cx - r, cy - r, cx + r, cy + r))
        side = 2 * r
        big = 4
        mask = Image.new("L", (side * big, side * big), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, side * big - 1, side * big - 1), fill=255)
        img.putalpha(mask.resize((side, side), Image.LANCZOS))
        img = img.resize((224, 224), Image.LANCZOS)
        img.save(out, "WEBP", quality=84, method=6)
    else:
        # The lantern is painted on black: the black becomes see-through, so it can hang over anything.
        img = crop_to(img, 3 / 4).resize((480, 640), Image.LANCZOS)
        light = img.convert("HSV").getchannel("V")
        alpha = light.point(lambda v: 0 if v < 14 else 255 if v > 64 else round((v - 14) * 255 / 50)).filter(ImageFilter.GaussianBlur(1.2))
        img.putalpha(alpha)
        # Cut close around the lantern, then set it on a 3:4 sheet so it fills its frame.
        left, top, right, bottom = alpha.point(lambda v: 255 if v > 40 else 0).getbbox() or (0, 0, *img.size)
        cut = img.crop((left, top, right, bottom))
        scale = min(360 * 0.94 / cut.width, 480 * 0.94 / cut.height)
        cut = cut.resize((round(cut.width * scale), round(cut.height * scale)), Image.LANCZOS)
        img = Image.new("RGBA", (360, 480), (0, 0, 0, 0))
        img.paste(cut, ((360 - cut.width) // 2, (480 - cut.height) // 2))
        img.save(out, "WEBP", quality=82, method=6)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="which pictures (default: all)")
    ap.add_argument("--raw", required=True, help="folder for the pictures as the model returned them")
    ap.add_argument("--pack-only", action="store_true", help="only cut and convert what the raw folder already holds")
    ap.add_argument("--redo", action="store_true", help="ask again even if the raw picture is there")
    args = ap.parse_args()

    raw_dir = Path(args.raw)
    raw_dir.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    names = args.names or list(PICTURES)
    asked = 0
    for name in names:
        kind, aspect, prompt = PICTURES[name]
        raw = raw_dir / f"{name}.png"
        if not args.pack_only and (args.redo or not raw.exists()):
            try:
                raw.write_bytes(ask(prompt, aspect))
                asked += 1
                print(f"asked   {name}")
            except RuntimeError as e:
                print(f"FAILED  {name}: {e}")
                continue
            time.sleep(3.5)
        if raw.exists():
            out = pack(name, kind, raw)
            print(f"packed  {name} -> {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
    print(f"{asked} picture(s) asked for")


if __name__ == "__main__":
    main()
