"""Lettura della configurazione e del formato episodio.

Formato di un episodio (cartella episodes/<slug>/):
  episode.yaml  metadati (titolo, descrizione, data di uscita, stato, miniatura, fonti)
  script.md     narrazione: '# Capitolo', '@image <rif>', '@pause <sec>', paragrafi di testo
  shorts.yaml   3 Shorts ricavati dall'episodio
  thumbnail.png (facoltativa) miniatura fatta nella sessione della domenica

Riferimenti immagine:
  commons:File:Nome.jpg      file preciso su Wikimedia Commons
  search:parole chiave       ricerca su Wikimedia Commons (solo licenze libere)
  nasa:parole chiave         ricerca nella libreria immagini NASA
  local:images/nome.jpg      file nella cartella dell'episodio (es. creato con Gemini)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    with open(ROOT / "config" / "channel.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class Paragraph:
    text: str
    sentences: list[str]


@dataclass
class Scene:
    images: list[str]
    paragraphs: list[Paragraph] = field(default_factory=list)
    chapter: int = 0
    pause_after: float = 0.0


@dataclass
class Chapter:
    title: str
    index: int


@dataclass
class Script:
    chapters: list[Chapter]
    scenes: list[Scene]

    @property
    def word_count(self) -> int:
        return sum(len(p.text.split()) for s in self.scenes for p in s.paragraphs)


_SENT_RE = re.compile(r"(?<=[.!?…])[\"”’)]*\s+(?=[A-Z0-9\"“‘(])")
_ABBREVS = ("Mr.", "Mrs.", "Dr.", "St.", "c.", "ca.", "vs.", "Mt.", "B.C.", "A.D.")


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    raw_parts = _SENT_RE.split(text)
    parts: list[str] = []
    for rp in raw_parts:
        if parts and parts[-1].endswith(_ABBREVS):
            parts[-1] = f"{parts[-1]} {rp}"
        else:
            parts.append(rp)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # frasi molto lunghe: Kokoro regge ~500 token, ma spezziamo per ritmo e sottotitoli
        if len(p) > 380:
            chunks = re.split(r"(?<=[;:,])\s+", p)
            buf = ""
            for c in chunks:
                if len(buf) + len(c) > 300 and buf:
                    out.append(buf.strip())
                    buf = c
                else:
                    buf = f"{buf} {c}" if buf else c
            if buf:
                out.append(buf.strip())
        else:
            out.append(p)
    return out


def parse_script(path: Path) -> Script:
    chapters: list[Chapter] = []
    scenes: list[Scene] = []
    para_buf: list[str] = []
    pending_images: list[str] = []

    def current_scene() -> Scene:
        nonlocal pending_images
        if pending_images:
            scenes.append(Scene(images=pending_images, chapter=max(len(chapters) - 1, 0)))
            pending_images = []
        if not scenes:
            raise ValueError(f"{path}: il testo inizia prima di un '@image'")
        return scenes[-1]

    def flush_para():
        if para_buf:
            text = " ".join(para_buf).strip()
            para_buf.clear()
            if text:
                current_scene().paragraphs.append(Paragraph(text, split_sentences(text)))

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("<!--") or line.startswith("//"):
            continue
        if line.startswith("# "):
            flush_para()
            chapters.append(Chapter(line[2:].strip(), len(chapters)))
            continue
        if line.startswith("@image"):
            flush_para()
            ref = line[len("@image"):].strip()
            if scenes and not scenes[-1].paragraphs and not pending_images:
                scenes[-1].images.append(ref)  # più immagini nella stessa scena
            else:
                pending_images.append(ref)
            continue
        if line.startswith("@pause"):
            flush_para()
            sec = float(line.split()[1])
            if scenes:
                scenes[-1].pause_after += sec
            continue
        if not line:
            flush_para()
            continue
        para_buf.append(line)
    flush_para()
    if pending_images:
        raise ValueError(f"{path}: '@image' finale senza testo")
    if not chapters:
        chapters.append(Chapter("Introduction", 0))
    return Script(chapters=chapters, scenes=scenes)


def load_episode(ep_dir: Path) -> dict:
    with open(ep_dir / "episode.yaml", encoding="utf-8") as f:
        meta = yaml.safe_load(f)
    meta["_dir"] = ep_dir
    return meta


def load_shorts(ep_dir: Path) -> list[dict]:
    p = ep_dir / "shorts.yaml"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("shorts", [])
