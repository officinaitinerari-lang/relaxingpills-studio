"""Voce: Kokoro (modello locale gratuito), frase per frase con tempi esatti."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
import soundfile as sf
import yaml

from .spec import ROOT, Script

SR = 24000
MODEL_DIR = Path(os.environ.get("RP_MODEL_DIR", Path.home() / ".cache" / "relaxingpills" / "models"))


@dataclass
class Cue:
    start: float
    end: float
    text: str
    scene: int
    chapter: int


def ensure_models(cfg: dict) -> tuple[Path, Path]:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for key, name in (("model_url", "kokoro.onnx"), ("voices_url", "voices.bin")):
        dest = MODEL_DIR / name
        if not dest.exists() or dest.stat().st_size < 1_000_000:
            print(f"  scarico {name}…")
            with requests.get(cfg["voice"][key], stream=True, timeout=600) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
        out.append(dest)
    return out[0], out[1]


def _load_pronunciations() -> list[tuple[re.Pattern, str]]:
    p = ROOT / "config" / "pronunciations.yaml"
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    rules = []
    for word, say in (data.get("words") or {}).items():
        rules.append((re.compile(rf"\b{re.escape(word)}\b"), say))
    return rules


class Narrator:
    def __init__(self, cfg: dict):
        from kokoro_onnx import Kokoro
        model, voices = ensure_models(cfg)
        self.k = Kokoro(str(model), str(voices))
        self.v = cfg["voice"]
        self.rules = _load_pronunciations()

    def _prep(self, text: str) -> str:
        for rx, say in self.rules:
            text = rx.sub(say, text)
        # numeri romani nei nomi propri e simboli che Kokoro legge male
        text = text.replace("—", ", ").replace("–", " to ").replace("&", " and ")
        return text

    def say(self, text: str, speed: float) -> np.ndarray:
        samples, sr = self.k.create(self._prep(text), voice=self.v["voice"], speed=speed, lang=self.v["lang"])
        assert sr == SR, sr
        return samples.astype(np.float32)


def silence(sec: float) -> np.ndarray:
    return np.zeros(int(round(sec * SR)), dtype=np.float32)


def narrate_script(script: Script, cfg: dict, out_wav: Path, narrator: Narrator | None = None):
    """Scrive la voce su WAV progressivamente. Ritorna (cues, scene_bounds, chapter_starts, durata)."""
    v = cfg["voice"]
    narrator = narrator or Narrator(cfg)
    speed = v["speed_long"]
    cues: list[Cue] = []
    scene_bounds: list[tuple[float, float]] = []
    chapter_starts: dict[int, float] = {}
    t = 0.0
    with sf.SoundFile(out_wav, "w", samplerate=SR, channels=1, subtype="PCM_16") as f:
        def write(a: np.ndarray):
            nonlocal t
            f.write(a)
            t += len(a) / SR

        write(silence(v["intro_silence"]))
        prev_chapter = None
        n_sent = sum(len(p.sentences) for s in script.scenes for p in s.paragraphs)
        done = 0
        for si, scene in enumerate(script.scenes):
            scene_start = t if si else 0.0
            if prev_chapter is not None and scene.chapter != prev_chapter:
                write(silence(v["pause_chapter"]))
            if scene.chapter not in chapter_starts:
                chapter_starts[scene.chapter] = scene_start
            for pi, para in enumerate(scene.paragraphs):
                for k, sent in enumerate(para.sentences):
                    audio = narrator.say(sent, speed)
                    start = t
                    write(audio)
                    cues.append(Cue(start, t, sent, si, scene.chapter))
                    if k < len(para.sentences) - 1:
                        write(silence(v["pause_sentence"]))
                    done += 1
                    if done % 50 == 0:
                        print(f"  voce: {done}/{n_sent} frasi, {t/60:.1f} min")
                write(silence(v["pause_paragraph"]))
            if scene.pause_after > 0:
                write(silence(scene.pause_after))
            prev_chapter = scene.chapter
            scene_bounds.append((scene_start, t))
        write(silence(v["outro_silence"]))
        # l'ultima scena copre anche il silenzio finale
        if scene_bounds:
            scene_bounds[-1] = (scene_bounds[-1][0], t)
    return cues, scene_bounds, chapter_starts, t


def narrate_text(text: str, cfg: dict, out_wav: Path, narrator: Narrator, speed: float, lead: float = 0.3, tail: float = 0.8):
    """Per gli Shorts: testo breve, frase per frase."""
    from .spec import split_sentences
    cues = []
    t = 0.0
    with sf.SoundFile(out_wav, "w", samplerate=SR, channels=1, subtype="PCM_16") as f:
        f.write(silence(lead)); t += lead
        for sent in split_sentences(text):
            a = narrator.say(sent, speed)
            cues.append(Cue(t, t + len(a) / SR, sent, 0, 0))
            f.write(a); t += len(a) / SR
            f.write(silence(0.18)); t += 0.18
        f.write(silence(tail)); t += tail
    return cues, t
