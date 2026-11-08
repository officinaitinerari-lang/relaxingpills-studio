"""Punto d'ingresso: costruisce e carica gli episodi pronti.

  python -m studio.run                 tutti gli episodi con status: ready non ancora caricati
  python -m studio.run --episode SLUG  un episodio preciso
  python -m studio.run --no-upload     solo montaggio e controlli (prova)
  python -m studio.run --offline       senza rete (immagini sostitutive), per test locali
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .spec import ROOT, load_config, load_episode

EPISODES = ROOT / "episodes"


def load_state(ep_dir: Path) -> dict:
    p = ep_dir / "published.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_state(ep_dir: Path, state: dict) -> None:
    (ep_dir / "published.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def playlists() -> dict:
    p = ROOT / "config" / "playlists.yaml"
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def pending_episodes(only: str | None) -> list[Path]:
    out = []
    for d in sorted(EPISODES.iterdir()):
        if not d.is_dir() or not (d / "episode.yaml").exists():
            continue
        if only and d.name != only:
            continue
        if not only and d.name.startswith(("_", ".")):
            continue
        meta = load_episode(d)
        st = load_state(d)
        if only or (meta.get("status") == "ready" and not st.get("complete")):
            out.append(d)
    return out


def summary(line: str) -> None:
    print(line)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def upload_episode(ep_dir: Path, report: dict, cfg: dict) -> dict:
    from . import youtube as Y
    meta = load_episode(ep_dir)
    state = load_state(ep_dir)
    yt = Y.client()
    pls = playlists()
    out = Path(report["outputs"]["long"]).parent
    desc = Path(report["outputs"]["description"]).read_text(encoding="utf-8")

    if not state.get("long"):
        r = Y.upload_video(yt, Path(report["outputs"]["long"]), meta["title"], desc, report["tags"], cfg, meta.get("publish_at"))
        r["thumbnail"] = Y.set_thumbnail(yt, r["video_id"], Path(report["outputs"]["thumbnail"]))
        r["captions"] = Y.add_captions(yt, r["video_id"], Path(report["outputs"]["srt"]))
        r["playlist"] = Y.add_to_playlist(yt, pls.get(meta.get("pillar", "history"), ""), r["video_id"])
        state["long"] = r
        save_state(ep_dir, state)
        summary(f"- Video lungo caricato: https://youtu.be/{r['video_id']} (uscita {r['publish_at']}) · miniatura {r['thumbnail']}")
    long_url = f"https://youtu.be/{state['long']['video_id']}"

    state.setdefault("shorts", {})
    for sh_meta, sh in zip(_shorts_meta(ep_dir), report.get("shorts", [])):
        key = str(sh["index"])
        if key in state["shorts"]:
            continue
        d = (sh_meta.get("description") or "").strip()
        d = f"{d}\n\nFull calm episode: {long_url}\n\n#shorts #history #science".strip()
        tags = list(dict.fromkeys((sh_meta.get("tags") or []) + report["tags"][:8]))
        r = Y.upload_video(yt, Path(sh["path"]), sh["title"], d, tags, cfg, sh.get("publish_at"))
        state["shorts"][key] = r
        save_state(ep_dir, state)
        summary(f"- Short {key} caricato: https://youtu.be/{r['video_id']} (uscita {r['publish_at']})")

    n_sh = len(report.get("shorts", []))
    state["complete"] = bool(state.get("long")) and len(state["shorts"]) >= n_sh
    state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_state(ep_dir, state)
    return state


def _shorts_meta(ep_dir: Path) -> list[dict]:
    from .spec import load_shorts
    return load_shorts(ep_dir)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--skip-shorts", action="store_true")
    a = ap.parse_args()

    cfg = load_config()
    eps = pending_episodes(a.episode)
    if not eps:
        summary("Nessun episodio da costruire.")
        return 0
    eps = eps[: cfg["run"]["max_long_per_run"]]

    from . import youtube as Y
    from .build import build_episode
    from .tts import Narrator
    upload = not a.no_upload and Y.has_credentials()
    if not a.no_upload and not upload:
        if not a.episode:
            summary("Credenziali YouTube non ancora configurate: nessun montaggio automatico. "
                    "Per una prova lancia il workflow a mano con 'Solo prova'.")
            return 0
        summary("⚠️ Credenziali YouTube assenti: costruisco senza caricare.")

    narrator = Narrator(cfg)
    failed = 0
    for ep in eps:
        summary(f"## {ep.name}")
        try:
            rep = build_episode(ep, offline=a.offline, skip_shorts=a.skip_shorts, narrator=narrator)
        except Exception as e:
            summary(f"❌ Errore nel montaggio: {e}")
            failed += 1
            continue
        for c in rep["checks"]:
            if not c["ok"]:
                summary(f"- {'❌' if c['fatal'] else '⚠️'} {c['name']}: {c['detail']}")
        summary(f"- Durata {rep['duration_min']} min · {rep['words']} parole · miniatura {rep.get('thumbnail_source')}")
        if not rep["ok"]:
            summary("❌ Controlli non superati: niente caricamento.")
            failed += 1
            continue
        if upload:
            try:
                upload_episode(ep, rep, cfg)
            except Exception as e:
                summary(f"❌ Errore nel caricamento: {e}")
                failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
