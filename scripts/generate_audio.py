#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "assets" / "audio"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# (id, model, prompt, max_duration_sec, is_music)
AUDIO_SPECS: list[tuple[str, str, str, float, bool]] = [
    (
        "tavern_theme",
        "google/lyria-3-clip-preview",
        "Instrumental cozy medieval fantasy tavern music, lively lute, warm fiddle, flute, gentle wooden tavern hearth ambience, upbeat hearthstone tavern mood, no vocals",
        30.0,
        True,
    ),
    (
        "battle_theme",
        "google/lyria-3-pro-preview",
        "Instrumental epic medieval fantasy card duel soundtrack, heroic orchestral strings, Celtic bodhran war drums, brass horn melody, steady energetic tempo, loopable, no vocals",
        36.0,
        True,
    ),
    (
        "victory_fanfare",
        "google/lyria-3-clip-preview",
        "Short bright heroic medieval brass trumpet and orchestral victory fanfare chord flourish, triumphant 2-second stinger followed by silence, crisp studio recording, no vocals",
        2.8,
        False,
    ),
    (
        "defeat_stinger",
        "google/lyria-3-clip-preview",
        "Short dramatic descending low brass horn and deep war drum defeat stinger, somber 2-second medieval cue followed by silence, crisp recording, no vocals",
        2.6,
        False,
    ),
    (
        "turn_horn",
        "google/lyria-3-clip-preview",
        "Single crisp warm medieval tavern brass bell and chime double-note cue, bright clean 1-second notification stinger followed by silence, no background music, no vocals",
        1.1,
        False,
    ),
    (
        "spell_chime",
        "google/lyria-3-clip-preview",
        "Single magical fantasy harp glissando and crystalline arcane chime shimmer, bright clean 1-second spell cast sound effect followed by silence, no beat, no vocals",
        0.95,
        False,
    ),
    (
        "hero_power",
        "google/lyria-3-clip-preview",
        "Single resonant fantasy bell chime with subtle golden shimmer chord, crisp clean 0.8-second ability activation sound followed by silence, no drums, no vocals",
        0.85,
        False,
    ),
    (
        "attack_clash",
        "google/lyria-3-clip-preview",
        "Single heavy percussive medieval sword clash and wooden shield slam impact sound effect, punchy transient 0.5-second hit followed by silence, no music, no vocals",
        0.55,
        False,
    ),
    (
        "card_play",
        "google/lyria-3-clip-preview",
        "Single crisp heavy card slap onto a wooden tavern table with deep warm wooden thump, clean 0.35-second foley sound effect followed by silence, no music, no vocals",
        0.4,
        False,
    ),
    (
        "ui_click",
        "google/lyria-3-clip-preview",
        "Single subtle wooden button click and soft brass latch tick, very short 0.15-second UI sound effect followed by silence, no music, no vocals",
        0.2,
        False,
    ),
]


def fetch_lyria_mp3(api_key: str, model: str, prompt: str) -> bytes:
    r = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "stream": True,
            "modalities": ["audio", "text"],
            "messages": [{"role": "user", "content": prompt}],
        },
        stream=True,
        timeout=180,
    )
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    chunks: list[bytes] = []
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break
        obj = json.loads(payload)
        delta = (obj.get("choices") or [{}])[0].get("delta") or {}
        audio = delta.get("audio")
        if audio and audio.get("data"):
            chunks.append(base64.b64decode(audio["data"]))
    if not chunks:
        raise RuntimeError("No audio data returned in stream")
    return b"".join(chunks)


def process_mp3(raw_bytes: bytes, out_path: Path, max_dur: float, is_music: bool) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
        tmp.write(raw_bytes)
        tmp.flush()

        fade_len = 1.5 if is_music else min(0.12, max_dur * 0.3)
        fade_start = max(0.05, max_dur - fade_len)
        if is_music:
            # Trim leading silence, normalize, apply smooth intro/outro fades for clean looping
            af = (
                f"silenceremove=start_periods=1:start_threshold=-45dB,"
                f"atrim=0:{max_dur},"
                f"afade=t=in:st=0:d=0.6,"
                f"afade=t=out:st={fade_start:.2f}:d={fade_len:.2f},"
                f"loudnorm=I=-18:TP=-2:LRA=9"
            )
            bitrate = "112k"
        else:
            # Strip leading silence so SFX triggers instantaneously (<10ms latency), normalize & fade tail
            af = (
                f"silenceremove=start_periods=1:start_threshold=-35dB,"
                f"atrim=0:{max_dur},"
                f"afade=t=out:st={fade_start:.2f}:d={fade_len:.2f},"
                f"loudnorm=I=-14:TP=-1.5:LRA=7"
            )
            bitrate = "96k"

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                tmp.name,
                "-af",
                af,
                "-codec:a",
                "libmp3lame",
                "-b:a",
                bitrate,
                str(out_path),
            ],
            check=True,
        )


def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENROUTER_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Reuse /tmp/test_lyria_clip.bin for tavern_theme if present
    cached_tavern = Path("/tmp/test_lyria_clip.bin")
    tavern_out = AUDIO_DIR / "tavern_theme.mp3"
    if not tavern_out.exists() and cached_tavern.exists() and cached_tavern.stat().st_size > 10000:
        print("Processing cached tavern_theme from /tmp/test_lyria_clip.bin...")
        process_mp3(cached_tavern.read_bytes(), tavern_out, 30.0, True)
        print(f"  saved {tavern_out.name} ({tavern_out.stat().st_size // 1024}KB)")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    pending = [
        spec for spec in AUDIO_SPECS
        if not (AUDIO_DIR / f"{spec[0]}.mp3").exists() or (AUDIO_DIR / f"{spec[0]}.mp3").stat().st_size <= 1000
    ]
    if not pending:
        print("All audio assets cached.")
        return

    def _run(spec: tuple[str, str, str, float, bool]) -> tuple[str, str]:
        item_id, model, prompt, max_dur, is_music = spec
        out_path = AUDIO_DIR / f"{item_id}.mp3"
        raw = fetch_lyria_mp3(api_key, model, prompt)
        process_mp3(raw, out_path, max_dur, is_music)
        return item_id, f"{out_path.stat().st_size // 1024}KB"

    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {pool.submit(_run, sp): sp[0] for sp in pending}
        for fut in as_completed(futs):
            item_id = futs[fut]
            try:
                iid, sz = fut.result()
                print(f"[ok] {iid}.mp3 ({sz})", flush=True)
            except Exception as e:
                print(f"[err] {item_id}: {e}", flush=True)


if __name__ == "__main__":
    main()
