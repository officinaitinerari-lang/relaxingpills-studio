"""Controllo veloce di un episodio scritto (senza generare audio o video).

  python -m studio.check episodes/2026-12-01-ancient-rome
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from .spec import load_config, load_episode, load_shorts, parse_script

WPM = 120  # parole al minuto della voce a velocità 0.88


def check(ep_dir: Path) -> bool:
    cfg = load_config()
    errs, warns = [], []
    meta = load_episode(ep_dir)
    for k in ("status", "pillar", "publish_at", "title", "description", "tags", "thumbnail", "sources"):
        if not meta.get(k):
            errs.append(f"episode.yaml: manca '{k}'")
    if meta.get("pillar") not in ("history", "science"):
        errs.append("pillar deve essere history o science")
    try:
        datetime.fromisoformat(str(meta.get("publish_at")))
    except Exception:
        errs.append("publish_at non valido (formato 2026-12-01T02:00)")
    title = meta.get("title", "")
    if len(title) > 100:
        errs.append("titolo oltre 100 caratteri")
    elif len(title) > 75:
        warns.append("titolo oltre 75 caratteri: su telefono viene tagliato")
    kw = (meta.get("keyword") or "").lower()
    if not kw:
        errs.append("manca 'keyword' (parola chiave principale scelta con la ricerca vidIQ)")
    else:
        if kw.split(" for ")[0] not in title.lower() and kw not in title.lower():
            warns.append(f"la parola chiave '{kw}' non compare nel titolo")
        first = (meta.get("description") or "").strip().split("\n")[0].lower()
        if kw not in first:
            errs.append("la parola chiave deve comparire nella prima riga della descrizione")
    if not re.search(r"\|\s*(History|Science) for Sleep", title):
        errs.append("il titolo deve finire con '| History for Sleep' o '| Science for Sleep'")
    pa = str(meta.get("publish_at", ""))
    if pa and not pa.endswith("Z"):
        warns.append("publish_at senza 'Z': usare l'orario UTC (es. 2026-12-01T00:00Z)")
    locs = meta.get("localizations") or {}
    missing = [l for l in ("es", "pt", "fr", "de", "it") if not (locs.get(l) or {}).get("title")]
    if missing:
        errs.append(f"mancano titolo/descrizione tradotti per: {', '.join(missing)}")
    if len(meta.get("tags") or []) < 8:
        warns.append("meno di 8 tag")

    script = parse_script(ep_dir / "script.md")
    words = script.word_count
    minutes = words / WPM
    lo = meta.get("min_minutes", cfg["qa"]["long_min_minutes"])
    hi = meta.get("max_minutes", cfg["qa"]["long_max_minutes"])
    if not lo <= minutes <= hi:
        errs.append(f"durata stimata {minutes:.0f} min fuori da {lo}-{hi} ({words} parole)")
    n_img = sum(len(s.images) for s in script.scenes)
    per_img = words / max(n_img, 1)
    if per_img > 200:
        errs.append(f"troppe poche immagini: una ogni {per_img:.0f} parole (max 200)")
    for s in script.scenes:
        w = sum(len(p.text.split()) for p in s.paragraphs) / len(s.images)
        if w > 320:
            warns.append(f"scena lunga ({w:.0f} parole per immagine) nel capitolo {script.chapters[s.chapter].title!r}")
    for s in script.scenes:
        for ref in s.images:
            kind = ref.split(":", 1)[0]
            if kind not in ("commons", "search", "nasa", "local"):
                errs.append(f"riferimento immagine non valido: {ref}")
            if kind == "local" and not (ep_dir / ref.split(":", 1)[1].strip()).exists():
                errs.append(f"file locale mancante: {ref}")
    if len(script.chapters) < 3:
        errs.append("servono almeno 3 capitoli")
    long_sent = [x for s in script.scenes for p in s.paragraphs for x in p.sentences if len(x.split()) > 45]
    if long_sent:
        warns.append(f"{len(long_sent)} frasi oltre 45 parole (spezzarle aiuta la voce)")

    shorts = load_shorts(ep_dir)
    if len(shorts) != 3:
        warns.append(f"{len(shorts)} Shorts invece di 3")
    for i, sh in enumerate(shorts, 1):
        n = len(sh.get("text", "").split())
        if not 70 <= n <= 140:
            errs.append(f"Short {i}: {n} parole (servono 70-140)")
        if not sh.get("title"):
            errs.append(f"Short {i}: manca il titolo")
        if not sh.get("images"):
            errs.append(f"Short {i}: nessuna immagine")

    print(f"{ep_dir.name}: {words} parole ≈ {minutes:.0f} min · {len(script.chapters)} capitoli · {n_img} immagini "
          f"(una ogni {per_img:.0f} parole) · {len(shorts)} Shorts")
    for w in warns:
        print("  ⚠️ ", w)
    for e in errs:
        print("  ❌", e)
    print("OK" if not errs else "DA CORREGGERE")
    return not errs


if __name__ == "__main__":
    ok = all(check(Path(p)) for p in sys.argv[1:])
    sys.exit(0 if ok else 1)
