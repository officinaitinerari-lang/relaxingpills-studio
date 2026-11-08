"""Operazioni una tantum sul canale (lanciate a mano dal workflow 'Manutenzione canale').

  verify      controlla che le credenziali funzionino e stampa i dati del canale
  playlists   crea (se mancano) le playlist e salva gli ID in config/playlists.yaml
  branding    aggiorna descrizione e parole chiave del canale
  unlist-old  rende "non in elenco" i video vecchi elencati in config/old_videos.yaml
"""
from __future__ import annotations

import argparse
import sys

import yaml

from . import youtube as Y
from .spec import ROOT

CHANNEL_DESCRIPTION = """Calm history & science for sleep.

Relaxing Pills tells real stories from the past and the universe in a slow, gentle voice: daily life in ancient Rome, the world of the samurai, the giant planets, the quiet forces that shape the Earth. Every episode is long, softly paced and built on original research, with public-domain art and calm ambient music, so you can learn something beautiful while you drift off.

New long episodes every week, plus short "pills" of history and science.

Put on your headphones, dim the lights, and let the story carry you.

Narration is AI-assisted; scripts and research are original, with sources listed in every description."""

KEYWORDS = '"history for sleep" "science for sleep" "sleep documentary" "calm history" "bedtime stories for adults" "relaxing history" "space for sleep"'

PLAYLISTS = {
    "history": ("Calm History for Sleep", "Long, gentle history episodes from Relaxing Pills: real stories, softly told, made for sleep."),
    "science": ("Calm Science for Sleep", "Long, gentle science episodes from Relaxing Pills: planets, the Earth and the universe, softly told."),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["verify", "playlists", "branding", "unlist-old"])
    a = ap.parse_args()
    if not Y.has_credentials():
        print("Credenziali YouTube assenti nei secret del repository.")
        return 1
    yt = Y.client()
    if a.action == "verify":
        ch = Y.channel_info(yt)
        print("Canale:", ch.get("snippet", {}).get("title"), ch.get("id"))
        print("Statistiche:", ch.get("statistics"))
        print("Stato:", ch.get("status"))
        return 0
    if a.action == "playlists":
        ids = {k: Y.ensure_playlist(yt, t, d) for k, (t, d) in PLAYLISTS.items()}
        (ROOT / "config" / "playlists.yaml").write_text(yaml.safe_dump(ids), encoding="utf-8")
        print("Playlist:", ids)
        return 0
    if a.action == "branding":
        print("Descrizione canale:", Y.update_channel_branding(yt, CHANNEL_DESCRIPTION, KEYWORDS))
        return 0
    if a.action == "unlist-old":
        data = yaml.safe_load((ROOT / "config" / "old_videos.yaml").read_text(encoding="utf-8"))
        bad = 0
        for vid in data.get("unlist", []):
            r = Y.set_privacy(yt, vid, "unlisted")
            print(vid, r)
            bad += r != "ok"
        return 1 if bad else 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
