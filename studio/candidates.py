"""Ricerca dei candidati immagine per ogni scena, con griglie visive da controllare.

Input:  episodes/<slug>/image_queries.yaml
  scenes:
    - id: s001
      text: "Dawn over the Forum: shopkeepers lift their wooden shutters"   # cosa dice la narrazione
      queries: ["Roman Forum painting", "Campo Vaccino"]                    # 1-3 ricerche precise
      science: false                                                       # true = cerca anche su NASA
      rerun: true                                                          # facoltativo: rifai solo queste scene

Output (cartella di uscita, poi pubblicata sul branch "candidati"):
  <slug>/candidates.json      per ogni scena fino a 8 candidati con riferimento esatto, titolo, autore, licenza, dimensioni
  <slug>/grids/<id>.jpg       griglia numerata dei candidati, da guardare prima di scegliere

  python -m studio.candidates episodes/<slug> <cartella_uscita>
"""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .images import Sources
from .spec import load_config

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
MIN_SIDE = 1600   # sotto questa risoluzione un candidato non viene proposto (qualità)


def _font(size: int):
    try:
        return ImageFont.truetype(FONT, size, layout_engine=ImageFont.Layout.BASIC)
    except Exception:
        return ImageFont.load_default()


def _small_thumb(c: dict) -> str | None:
    if c.get("thumb"):
        return c["thumb"]
    url = c.get("url") or ""
    if "/thumb/" in url:  # miniatura Wikimedia: 400 px invece di 2400
        return url.replace("/2400px-", "/400px-")
    return url or None


def gather(src: Sources, scene: dict) -> list[dict]:
    pools: dict[str, list[dict]] = {"commons": [], "met": [], "aic": [], "cma": [], "nasa": []}
    for q in scene.get("queries", [])[:3]:
        try:
            pools["commons"] += [c for c in src.commons_search(q, limit=25) if max(c["width"], c["height"]) >= MIN_SIDE][:5]
        except Exception as e:
            print(f"  commons '{q}': {e}")
        museums = () if scene.get("science") else (("aic", src.aic_search, 4), ("cma", src.cma_search, 4))
        for name, fn, n in museums:
            try:
                pools[name] += [c for c in fn(q, limit=n) if not c["width"] or max(c["width"], c["height"]) >= MIN_SIDE]
            except Exception as e:
                print(f"  {name} '{q}': {e}")
        if scene.get("science"):
            try:
                pools["nasa"] += src.nasa_search(q, limit=4)
            except Exception as e:
                print(f"  nasa '{q}': {e}")
    print(f"  {scene['id']}: " + ", ".join(f"{k} {len(v)}" for k, v in pools.items()))
    # un po' da ogni fonte, senza doppioni, massimo 8
    seen, out = set(), []
    order = ["nasa", "commons", "met", "aic", "cma"] if scene.get("science") else ["commons", "met", "aic", "cma", "nasa"]
    while len(out) < 8 and any(pools.values()):
        for name in order:
            if pools[name]:
                c = pools[name].pop(0)
                if c["ref"] not in seen:
                    seen.add(c["ref"])
                    out.append(c)
                if len(out) >= 8:
                    break
    return out


def _txt(d, xy, text, fill, size):
    """Scrive testo senza mai fallire (caratteri non latini sostituiti)."""
    t = "".join(ch if ord(ch) < 0x2000 else "?" for ch in str(text or ""))
    try:
        d.text(xy, t, fill=fill, font=_font(size))
    except Exception:
        d.text(xy, t.encode("ascii", "replace").decode(), fill=fill)


def grid(src: Sources, scene: dict, cands: list[dict], dest: Path) -> None:
    tw, th, cols = 300, 200, 4
    rows = max(1, (len(cands) + cols - 1) // cols)
    W, H = cols * (tw + 10) + 10, 70 + rows * (th + 58)
    im = Image.new("RGB", (W, H), (245, 244, 240))
    d = ImageDraw.Draw(im)
    _txt(d, (10, 8), f"{scene['id']}", (20, 20, 20), 20)
    _txt(d, (90, 10), scene.get("text", "")[:120], (60, 60, 60), 15)
    _txt(d, (90, 32), scene.get("text", "")[120:240], (60, 60, 60), 15)
    for i, c in enumerate(cands):
        x, y = 10 + (i % cols) * (tw + 10), 64 + (i // cols) * (th + 58)
        tile = Image.new("RGB", (tw, th), (200, 200, 200))
        url = _small_thumb(c)
        try:
            r = src.get(url, timeout=60) if url else None
            if r is not None and r.status_code == 200:
                t = Image.open(BytesIO(r.content)).convert("RGB")
                if not c.get("width"):
                    c["preview_size"] = list(t.size)
                tile = ImageOps.contain(t, (tw, th))
                bg = Image.new("RGB", (tw, th), (30, 30, 30))
                bg.paste(tile, ((tw - tile.width) // 2, (th - tile.height) // 2))
                tile = bg
        except Exception as e:
            print(f"  anteprima {c['ref']}: {e}")
        im.paste(tile, (x, y))
        d.rectangle([x, y, x + 34, y + 26], fill=(0, 0, 0))
        _txt(d, (x + 7, y + 3), str(i + 1), (255, 255, 255), 18)
        size = f"{c['width']}x{c['height']}" if c.get("width") else "alta ris."
        _txt(d, (x, y + th + 4), f"{c['source'][:22]} · {size}", (90, 90, 90), 12)
        _txt(d, (x, y + th + 20), c.get("title", "")[:44], (20, 20, 20), 13)
        _txt(d, (x, y + th + 36), (c.get("artist") or c.get("date") or "")[:44], (90, 90, 90), 12)
    im.save(dest, quality=82)


def main(ep_dir: Path, out_root: Path) -> int:
    cfg = load_config()
    src = Sources(cfg)
    data = yaml.safe_load((ep_dir / "image_queries.yaml").read_text(encoding="utf-8")) or {}
    scenes = data.get("scenes", [])
    flagged = [s for s in scenes if s.get("rerun")]
    todo = flagged or scenes
    out = out_root / ep_dir.name
    (out / "grids").mkdir(parents=True, exist_ok=True)
    jpath = out / "candidates.json"
    result = json.loads(jpath.read_text(encoding="utf-8")) if jpath.exists() else {}
    for n, sc in enumerate(todo, 1):
        cands = gather(src, sc)
        grid(src, sc, cands, out / "grids" / f"{sc['id']}.jpg")
        result[sc["id"]] = {"text": sc.get("text", ""), "queries": sc.get("queries", []),
                            "candidates": [{k: c.get(k) for k in ("ref", "source", "title", "artist", "date", "description",
                                                                  "width", "height", "license", "page", "preview_size")}
                                           for c in cands]}
        print(f"[{n}/{len(todo)}] {sc['id']}: {len(cands)} candidati")
        jpath.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    empty = [k for k, v in result.items() if not v["candidates"]]
    print(f"Fatto: {len(result)} scene, {len(empty)} senza candidati {empty[:10]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
