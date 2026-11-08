"""Musica ambient generata da zero (nessun diritto di terzi).

Pad lenti a più voci con leggero chorus, accordi che cambiano ogni ~24 s con dissolvenza,
un filo di "aria" (rumore filtrato). Ogni episodio ha una progressione diversa,
scelta in modo deterministico dallo slug: varietà senza casualità tra un render e l'altro.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import lfilter

SR = 24000


def _midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


# progressioni (note MIDI); storia = più calde, scienza = più aperte
PROGRESSIONS = {
    "history": [
        [[50, 57, 62, 65, 69], [46, 53, 58, 62, 65], [48, 55, 60, 64, 67], [45, 52, 57, 60, 64]],
        [[43, 50, 55, 59, 62], [40, 47, 52, 55, 59], [36, 43, 48, 52, 55], [38, 45, 50, 54, 57]],
        [[45, 52, 57, 60, 64], [41, 48, 53, 57, 60], [43, 50, 55, 59, 62], [40, 47, 52, 55, 59]],
    ],
    "science": [
        [[48, 55, 62, 64, 71], [50, 57, 62, 66, 69], [45, 52, 59, 64, 67], [41, 48, 55, 60, 64]],
        [[41, 48, 57, 60, 67], [43, 50, 59, 62, 66], [40, 47, 55, 59, 64], [38, 45, 54, 57, 62]],
        [[46, 53, 60, 65, 69], [48, 55, 62, 67, 71], [43, 50, 57, 62, 66], [45, 52, 59, 64, 67]],
    ],
}


def generate(out_wav: Path, duration: float, seed_text: str, pillar: str = "history",
             slot: float = 24.0, xfade: float = 9.0, chunk_sec: float = 20.0) -> None:
    seed = int(hashlib.sha1(seed_text.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    progs = PROGRESSIONS.get(pillar, PROGRESSIONS["history"])
    prog = progs[seed % len(progs)]
    detune = rng.uniform(0.25, 0.7, size=8)
    lfo_f = rng.uniform(0.018, 0.045, size=8)
    lfo_p = rng.uniform(0, 2 * np.pi, size=8)
    n_total = int(duration * SR)
    # rumore "aria": filtro passa-basso a un polo, stato conservato tra i blocchi
    alpha = 0.015
    air_state = np.zeros(1)

    def chord_wave(notes, t):
        sig = np.zeros_like(t)
        for j, n in enumerate(notes):
            f = _midi(n)
            amp = 0.9 / (1 + 0.35 * j)  # note basse più presenti
            lfo = 0.65 + 0.35 * np.sin(2 * np.pi * lfo_f[j % 8] * t + lfo_p[j % 8])
            v = (np.sin(2 * np.pi * f * t)
                 + 0.6 * np.sin(2 * np.pi * (f + detune[j % 8]) * t + 1.3)
                 + 0.18 * np.sin(2 * np.pi * 2 * f * t + 0.7))
            sig += amp * lfo * v
        return sig

    with sf.SoundFile(out_wav, "w", samplerate=SR, channels=1, subtype="PCM_16") as f:
        pos = 0
        chunk = int(chunk_sec * SR)
        while pos < n_total:
            n = min(chunk, n_total - pos)
            t = (pos + np.arange(n)) / SR
            k = np.floor(t / slot).astype(int)
            local = t - k * slot
            # peso della transizione verso l'accordo successivo negli ultimi xfade secondi
            w_next = np.clip((local - (slot - xfade)) / xfade, 0, 1)
            w_next = 0.5 - 0.5 * np.cos(np.pi * w_next)
            out = np.zeros(n)
            for kk in np.unique(k):
                m = k == kk
                cur = prog[kk % len(prog)]
                nxt = prog[(kk + 1) % len(prog)]
                tt = t[m]
                out[m] = (1 - w_next[m]) * chord_wave(cur, tt) + w_next[m] * chord_wave(nxt, tt)
            noise = rng.standard_normal(n)
            air, air_state = lfilter([alpha], [1.0, -(1.0 - alpha)], noise, zi=air_state)
            out = out / 6.0 + 0.9 * air
            # dissolvenze di apertura e chiusura
            fade_in = np.clip(t / 6.0, 0, 1)
            fade_out = np.clip((duration - t) / 8.0, 0, 1)
            out *= fade_in * fade_out
            f.write((np.tanh(out * 0.9) * 0.5).astype(np.float32))
            pos += n
