#!/usr/bin/env python3
"""Turn the CC0 instrument recordings in var/music-raw/ into the small mono MP3s the music uses.

Sources (both CC0 1.0, by Versilian Studios / Sam Gossner):
  VSCO 2 Community Edition  https://github.com/sgossner/VSCO-2-CE
  Versilian Community Sample Library  https://github.com/sgossner/VCSL
Most of these sets name notes one octave below scientific pitch (C3 = middle C), so each
instrument's octave offset was measured from the recordings themselves and is applied here.
Output: frontend/public/music/<instrument>/<note>.mp3 and frontend/public/music/samples.json.
"""
import json, math, os, re, subprocess, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "var" / "music-raw"
OUT = ROOT / "frontend" / "public" / "music"
NOTE = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
SR = 44100

# instrument: octave offset of its file names, kept range (MIDI), seconds kept, fade-out seconds,
# smallest step between kept notes (semitones)
PITCHED = {
    'harp':      dict(off=12, lo=36, hi=86, secs=4.0, fade=1.2, step=3),
    'strum':     dict(off=12, lo=50, hi=81, secs=3.0, fade=0.8, step=3),
    'recorder':  dict(off=12, lo=65, hi=82, secs=3.2, fade=0.4, step=2),
    'violin':    dict(off=0,  lo=55, hi=93, secs=4.0, fade=0.6, step=3),
    'flute':     dict(off=12, lo=60, hi=93, secs=4.0, fade=0.6, step=3),
    'horn':      dict(off=12, lo=40, hi=72, secs=4.0, fade=0.6, step=2),
    'vlnEns':    dict(off=12, lo=55, hi=86, secs=6.0, fade=1.5, step=2),
    'celloEns':  dict(off=12, lo=36, hi=65, secs=6.0, fade=1.5, step=2),
    'celloPizz': dict(off=12, lo=31, hi=67, secs=1.6, fade=0.5, step=2),
}
# hits: output name -> (file name pattern, seconds, fade)
HITS = {
    'frame':      ('frame', r'HDrumL_Hit_v3_rr1', 1.6, 0.6),
    'frame2':     ('frame', r'HDrumL_Hit_v2_rr2', 1.6, 0.6),
    'frameMute':  ('frame', r'HDrumL_HitMuted_v2_rr1', 0.8, 0.3),
    'frameMute2': ('frame', r'HDrumL_HitMuted_v3_rr2', 0.8, 0.3),
    'frameHand':  ('frame', r'HDrumS_Hand_v1_rr1', 0.8, 0.3),
    'tamb':       ('tamb', r'Tamb1_Hit_v1_rr1', 1.0, 0.4),
    'tambShake':  ('tamb', r'Tamb1_Shake_rr1', 1.2, 0.4),
    'tambRoll':   ('tamb', r'Tamb1_Roll_v2_rr1', 2.5, 0.8),
    'bdrum':      ('bdrum', r'BDrumNew_hit_v5_rr1', 2.0, 0.8),
    'timp':       ('timp', r'Timpani1_Hit_v3_rr1', 3.0, 1.0),
    'timpLow':    ('timp', r'Timpani2_Hit_v3_rr1', 3.0, 1.0),
}


def name_midi(n):
    m = re.search(r'(?<![A-Za-z])([A-G]#?)(\d)(?!\d)', n)
    return None if not m else 12 * (int(m.group(2)) + 1) + NOTE[m.group(1)]


def midi_name(m):
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def load(p):
    raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', str(p), '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def detune_cents(x, midi):
    """How far the recording sits from equal temperament (A4 = 440), from its spectrum."""
    i = int(np.argmax(np.abs(x[:SR]))) + int(0.2 * SR)
    seg = x[i:i + SR]
    if len(seg) < SR // 2:
        return 0.0
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 1 << 18))
    f = 440 * 2 ** ((midi - 69) / 12)
    k = f * (1 << 18) / SR
    lo, hi = int(k * 0.97), int(k * 1.03) + 1
    peak = lo + int(np.argmax(spec[lo:hi]))
    return 1200 * math.log2(peak / k)


def shape(x, secs, fade, gain_target=None):
    # Start at the attack: drop silence before the first sample above -50 dB of the peak.
    peak = np.max(np.abs(x)) or 1.0
    start = int(np.argmax(np.abs(x) > peak * 10 ** (-50 / 20)))
    start = max(0, start - int(0.004 * SR))
    x = x[start:start + int(secs * SR)].copy()
    n = int(fade * SR)
    if len(x) > n:
        x[-n:] *= np.linspace(1, 0, n) ** 2
    x[: int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    return x


def body_rms(x):
    seg = x[int(0.03 * SR): int(0.8 * SR)]
    return float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 1e-9


def write(x, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(x, -1, 1).astype(np.float32).tobytes()
    subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-',
                    '-c:a', 'libmp3lame', '-b:a', '64k', str(path)], input=pcm, check=True)


def main():
    manifest = {'pitched': {}, 'hits': {}, 'license': 'CC0-1.0 (VSCO 2 CE, VCSL by Versilian Studios)'}
    for inst, cfg in PITCHED.items():
        found = []
        for p in sorted((RAW / inst).glob('*.wav')):
            m = name_midi(p.name)
            if m is None:
                continue
            m += cfg['off']
            if cfg['lo'] <= m <= cfg['hi']:
                found.append((m, p))
        found.sort()
        kept, last = [], -99
        for m, p in found:
            if m - last >= cfg['step']:
                kept.append((m, p))
                last = m
        notes, shaped = {}, []
        for m, p in kept:
            x = load(p)
            cents = detune_cents(x, m)
            if abs(cents) > 12:  # retune by resampling (a few cents changes the length by a hair)
                ratio = 2 ** (-cents / 1200)
                idx = np.arange(0, len(x) - 1, ratio)
                x = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
            shaped.append((m, shape(x, cfg['secs'], cfg['fade']), cents))
        # one loudness for the whole instrument: each note to the same body level, peaks kept below 0.9
        for m, x, cents in shaped:
            g = 0.18 / max(body_rms(x), 1e-6)
            g = min(g, 0.9 / (np.max(np.abs(x)) or 1))
            name = midi_name(m)
            write(x * g, OUT / inst / f"{name.replace('#', 's')}.mp3")
            notes[name] = f"{inst}/{name.replace('#', 's')}.mp3"
        manifest['pitched'][inst] = notes
        print(f"{inst:10s} {len(notes):2d} notes {min(notes, key=lambda n: 0)}… " +
              ' '.join(f"{midi_name(m)}({c:+.0f}c)" for m, _, c in shaped))
    for out, (inst, pat, secs, fade) in HITS.items():
        src = next((p for p in sorted((RAW / inst).glob('*.wav')) if re.search(pat, p.name)), None)
        if src is None:
            print('missing', out); continue
        x = shape(load(src), secs, fade)
        x = x * (0.9 / (np.max(np.abs(x)) or 1))
        write(x, OUT / 'hits' / f'{out}.mp3')
        manifest['hits'][out] = f'hits/{out}.mp3'
    (OUT / 'samples.json').write_text(json.dumps(manifest, indent=1))
    total = sum(f.stat().st_size for f in OUT.rglob('*.mp3'))
    print(f"{sum(1 for _ in OUT.rglob('*.mp3'))} files, {total / 1e6:.2f} MB")


if __name__ == '__main__':
    main()
