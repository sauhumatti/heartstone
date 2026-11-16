#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CARDS_PATH = ROOT / "data" / "cards.json"
ART_DIR = ROOT / "assets" / "art"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "recraft/recraft-v4.1-flash-v2:free"

STYLE_BASE = (
    "Painterly high-fantasy trading card game illustration, Warcraft Azeroth style, "
    "rich warm lighting, crisp silhouette, expressive brushwork, no text, no letters, "
    "no watermark, no borders, no UI frames"
)

CLASS_FLAVOR = {
    "MAGE": "arcane sapphire and frost magic",
    "HUNTER": "wild forest amber and primal beasts",
    "WARRIOR": "forged iron, crimson battle fury",
    "PALADIN": "radiant golden Holy Light and silver plate",
    "PRIEST": "luminous white-gold light and shadowy mist",
    "ROGUE": "moonlit shadows, emerald poison and daggers",
    "SHAMAN": "elemental lightning, storm clouds and totems",
    "WARLOCK": "fel violet-green demonic flames",
    "DRUID": "ancient emerald grove, moonlight and nature magic",
    "NEUTRAL": "classic medieval Azeroth fantasy tavern and adventure",
}

UI_ITEMS: list[tuple[str, str, str, tuple[int, int]]] = [
    (
        "board_bg",
        "16:9",
        f"Top-down view of an ornate carved oak and brushed bronze fantasy tavern game table board surface, subtle recessed arena center, warm candlelight on edges, {STYLE_BASE}",
        (1024, 576),
    ),
    (
        "card_back",
        "3:4",
        f"Ornate classic fantasy trading card back design, glowing blue arcane spiral gem in center, hammered bronze and gold filigree border, dark steel rivets, {STYLE_BASE}",
        (280, 384),
    ),
    (
        "hero_WARRIOR",
        "4:3",
        f"Hero portrait of Garrosh Hellscream, fierce brown-skinned orc warchief with heavy iron tusks armor and giant war axe, fiery red background, {STYLE_BASE}",
        (400, 296),
    ),
    (
        "hero_MAGE",
        "4:3",
        f"Hero portrait of Jaina Proudmoore, human archmage sorceress with blonde hair, blue and gold Kirin Tor robes, glowing frost and arcane runes in hands, {STYLE_BASE}",
        (400, 296),
    ),
    (
        "hero_HUNTER",
        "4:3",
        f"Hero portrait of Rexxar, half-ogre half-orc beastmaster wearing bear-mask hood and leather fur armor, forest campfires behind, {STYLE_BASE}",
        (400, 296),
    ),
    (
        "hero_PALADIN",
        "4:3",
        f"Hero portrait of Uther the Lightbringer, noble bearded human paladin in ornate golden-blue plate armor holding a glowing warhammer, radiant light, {STYLE_BASE}",
        (400, 296),
    ),
    (
        "hero_PRIEST",
        "4:3",
        f"Hero portrait of Anduin Wrynn, young human priest prince in white and gold vestments channeling warm golden healing light, cathedral glow, {STYLE_BASE}",
        (400, 296),
    ),
    (
        "hero_ROGUE",
        "4:3",
        f"Hero portrait of Valeera Sanguinar, agile blood elf rogue assassin in dark crimson and obsidian leather hood with glowing green-eyed focus and curved daggers, {STYLE_BASE}",
        (400, 296),
    ),
    (
        "hero_SHAMAN",
        "4:3",
        f"Hero portrait of Thrall, wise green-skinned orc shaman in Doomhammer plate and wolf-fur mantle, blue lightning crackling around him, {STYLE_BASE}",
        (400, 296),
    ),
    (
        "hero_WARLOCK",
        "4:3",
        f"Hero portrait of Gul'dan, hunched dark orc warlock in spiked bone robes, glowing fel-green and purple demonic energy swirling, {STYLE_BASE}",
        (400, 296),
    ),
    (
        "hero_DRUID",
        "4:3",
        f"Hero portrait of Malfurion Stormrage, ancient night elf archdruid with antlers, emerald beard and owl-feathered mantle in a glowing forest, {STYLE_BASE}",
        (400, 296),
    ),
    (
        "hero_JARAXXUS",
        "4:3",
        f"Hero portrait of Lord Jaraxxus, towering crimson Eredar demon lord with curved horns, glowing green eyes and burning fel fire armor, {STYLE_BASE}",
        (400, 296),
    ),
]


def build_card_prompt(card: dict) -> str:
    name = card["name"]
    ctype = card["type"]
    cclass = card.get("card_class", "NEUTRAL")
    race = card.get("race")
    text = card.get("text", "")
    flavor = CLASS_FLAVOR.get(cclass, CLASS_FLAVOR["NEUTRAL"])

    if ctype == "HERO_POWER":
        return f"Fantasy RPG ability icon painting for '{name}': {text}. {flavor}. Centered dramatic emblem, {STYLE_BASE}"
    if ctype == "WEAPON":
        return f"Close-up fantasy RPG weapon illustration of '{name}': ornate enchanted blade/axe/bow gleaming on dark anvil/pedestal, {flavor}. {text}. {STYLE_BASE}"
    if ctype == "SPELL":
        return f"Dramatic fantasy spell effect illustration for '{name}': {text}. {flavor}. Dynamic swirling magic, centered composition, {STYLE_BASE}"
    # MINION
    race_str = f"{race.lower()} creature, " if race else ""
    return (
        f"Fantasy character/creature card illustration of '{name}' ({race_str}{cclass.lower()}): "
        f"{text or 'iconic fantasy warrior/creature'}. {flavor}. Dynamic portrait framing, {STYLE_BASE}"
    )


def build_tasks(mode: str) -> list[tuple[str, str, str, tuple[int, int]]]:
    cards: dict[str, dict] = json.loads(CARDS_PATH.read_text(encoding="utf-8"))
    tasks: list[tuple[str, str, str, tuple[int, int]]] = []

    if mode in ("ui", "all"):
        tasks.extend(UI_ITEMS)
        for cid, c in sorted(cards.items()):
            if c["type"] == "HERO_POWER":
                tasks.append((cid, "1:1", build_card_prompt(c), (192, 192)))

    if mode in ("tokens", "all"):
        for cid, c in sorted(cards.items()):
            if not c["collectible"] and c["type"] in ("MINION", "SPELL", "WEAPON"):
                # Skip Choose One duplicate helper spell choices if unneeded, keep tokens
                if cid.startswith("VAN_EX1_154") or cid.startswith("VAN_EX1_155") or cid.startswith("VAN_EX1_160") or cid.startswith("VAN_EX1_164") or cid.startswith("VAN_EX1_165") or cid.startswith("VAN_EX1_166") or cid.startswith("VAN_EX1_178") or cid.startswith("VAN_EX1_573") or cid.startswith("VAN_NEW1_007") or cid.startswith("VAN_NEW1_008"):
                    if cid.endswith(("a", "b")) and c["type"] == "SPELL":
                        continue
                tasks.append((cid, "4:3", build_card_prompt(c), (320, 236)))

    if mode in ("cards", "all"):
        # Prioritize starter deck cards first so playable starter decks get art earliest!
        sys.path.insert(0, str(ROOT))
        from data.starter_decks import STARTER_DECKS
        priority_ids: list[str] = []
        seen = set()
        for d in STARTER_DECKS.values():
            for cid in d["cards"]:
                if cid not in seen:
                    seen.add(cid)
                    priority_ids.append(cid)
        for cid, c in sorted(cards.items()):
            if c["collectible"] and cid not in seen:
                seen.add(cid)
                priority_ids.append(cid)

        for cid in priority_ids:
            c = cards[cid]
            tasks.append((cid, "4:3", build_card_prompt(c), (320, 236)))

    return tasks


def generate_one(
    api_key: str,
    item_id: str,
    aspect_ratio: str,
    prompt: str,
    size: tuple[int, int],
    max_retries: int = 5,
) -> tuple[str, bool, str]:
    out_path = ART_DIR / f"{item_id}.webp"
    if out_path.exists() and out_path.stat().st_size > 1000:
        return item_id, True, "cached"

    delay = 3.0
    for attempt in range(max_retries):
        try:
            r = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "modalities": ["image"],
                    "image_config": {"aspect_ratio": aspect_ratio},
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=90,
            )
            if r.status_code == 429:
                retry_after = float(r.headers.get("Retry-After") or delay)
                time.sleep(min(30.0, retry_after + 0.5))
                delay = min(30.0, delay * 1.8)
                continue
            if r.status_code >= 500:
                time.sleep(delay)
                delay = min(20.0, delay * 1.5)
                continue
            if not r.ok:
                return item_id, False, f"HTTP {r.status_code}: {r.text[:200]}"

            data = r.json()
            imgs = data.get("choices", [{}])[0].get("message", {}).get("images") or []
            if not imgs:
                return item_id, False, "No image in response"
            url = imgs[0].get("image_url", {}).get("url", "")
            if "," not in url:
                return item_id, False, "Unexpected image URL format"
            raw_bytes = base64.b64decode(url.split(",", 1)[1])
            img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            img = img.resize(size, Image.Resampling.LANCZOS)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(out_path, format="WEBP", quality=82, method=4)
            return item_id, True, f"ok ({out_path.stat().st_size // 1024}KB)"
        except Exception as e:
            if attempt == max_retries - 1:
                return item_id, False, str(e)
            time.sleep(delay)
            delay = min(20.0, delay * 1.5)
    return item_id, False, "max retries exceeded"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Hearthstone Classic assets via OpenRouter Recraft v4.1 Flash V2")
    parser.add_argument("--mode", choices=["ui", "tokens", "cards", "all"], default="all")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Max new assets to generate (0 = unlimited)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    ART_DIR.mkdir(parents=True, exist_ok=True)
    all_tasks = build_tasks(args.mode)
    pending = [t for t in all_tasks if not (ART_DIR / f"{t[0]}.webp").exists() or (ART_DIR / f"{t[0]}.webp").stat().st_size <= 1000]
    if args.limit > 0:
        pending = pending[: args.limit]

    print(f"Mode={args.mode} | Total={len(all_tasks)} | Cached={len(all_tasks)-len(pending)} | Generating={len(pending)} (workers={args.workers})")
    if not pending:
        print("Nothing to generate; all assets cached.")
        return

    ok_cnt = 0
    fail_cnt = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(generate_one, api_key, tid, ar, pr, sz): tid for tid, ar, pr, sz in pending}
        for i, fut in enumerate(as_completed(futs), 1):
            tid, ok, msg = fut.result()
            if ok:
                ok_cnt += 1
            else:
                fail_cnt += 1
            if i % 10 == 0 or not ok or i == len(pending):
                elapsed = time.time() - t0
                rate = i / max(0.1, elapsed) * 60
                print(f"[{i}/{len(pending)}] {tid}: {msg} | ok={ok_cnt} fail={fail_cnt} ({rate:.1f}/min)", flush=True)


if __name__ == "__main__":
    main()
