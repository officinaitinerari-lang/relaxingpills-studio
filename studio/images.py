"""Reperimento immagini: Wikimedia Commons, NASA, file locali.

Solo opere di pubblico dominio o con licenza libera. Ogni immagine scaricata porta con sé
autore, licenza e pagina d'origine, che finiscono nei crediti della descrizione.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
NASA_API = "https://images-api.nasa.gov/search"


@dataclass
class ImageAsset:
    ref: str
    path: str | None          # file locale scaricato (None = mancante)
    source_url: str = ""
    page_url: str = ""
    title: str = ""
    artist: str = ""
    license: str = ""
    attribution_required: bool = False
    fallback: bool = False


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s).strip()


class ImageFinder:
    def __init__(self, cfg: dict, cache_dir: Path, offline: bool = False):
        self.cfg = cfg
        self.cache = cache_dir
        self.cache.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.used: set[str] = set()
        self.s = requests.Session()
        self.s.headers["User-Agent"] = cfg["channel"]["user_agent"]
        icfg = cfg["images"]
        self.min_width = icfg["min_width"]
        self.allowed = [a.lower() for a in icfg["allowed_licenses"]]
        self.prefer_pd = icfg.get("prefer_public_domain", True)

    # ------------------------------------------------------------------ util
    def _license_ok(self, lic: str) -> bool:
        l = (lic or "").lower()
        if not l or "nonfree" in l or "fair use" in l or "-nd" in l or " nd" in l or "-nc" in l or " nc" in l:
            return False
        return any(l.startswith(a) or a in l for a in self.allowed)

    @staticmethod
    def _is_pd(lic: str) -> bool:
        l = (lic or "").lower()
        return "public domain" in l or l.startswith("pd") or "cc0" in l or "no restrictions" in l

    def _download(self, url: str, ext_hint: str = ".jpg") -> str | None:
        key = hashlib.sha1(url.encode()).hexdigest()[:16]
        dest = self.cache / f"{key}{ext_hint}"
        if dest.exists() and dest.stat().st_size > 1000:
            return str(dest)
        for _ in range(3):
            try:
                r = self.s.get(url, timeout=60)
                if r.status_code == 200 and len(r.content) > 1000:
                    dest.write_bytes(r.content)
                    # verifica che sia un'immagine leggibile
                    with Image.open(dest) as im:
                        im.verify()
                    return str(dest)
            except Exception:
                continue
        return None

    # --------------------------------------------------------------- commons
    def _commons_query(self, params: dict) -> list[dict]:
        base = {
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 2400,
        }
        base.update(params)
        r = self.s.get(COMMONS_API, params=base, timeout=60)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        items = sorted(pages.values(), key=lambda p: p.get("index", 0))
        out = []
        for p in items:
            ii = (p.get("imageinfo") or [{}])[0]
            if not ii:
                continue
            md = ii.get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value", "")
            out.append({
                "title": p.get("title", ""),
                "width": ii.get("width", 0), "height": ii.get("height", 0),
                "mime": ii.get("mime", ""),
                "url": ii.get("thumburl") or ii.get("url"),
                "page": ii.get("descriptionurl", ""),
                "license": lic,
                "attr_req": md.get("AttributionRequired", {}).get("value", "") == "true",
                "artist": _strip_html(md.get("Artist", {}).get("value", "")),
            })
        return out

    def _pick(self, cands: list[dict], landscape: bool) -> dict | None:
        ok = [c for c in cands
              if c["mime"] in ("image/jpeg", "image/png", "image/tiff", "image/webp")
              and c["width"] >= self.min_width and self._license_ok(c["license"])
              and c["url"] not in self.used]
        if not ok:
            return None

        def score(i_c):
            i, c = i_c
            ratio = c["width"] / max(c["height"], 1)
            s = -i  # ordine di rilevanza
            if landscape:
                s += 4 if ratio >= 1.25 else (-6 if ratio < 0.9 else 0)
            else:
                s += 3 if ratio <= 1.0 else 0
            if self.prefer_pd and self._is_pd(c["license"]):
                s += 5
            return s

        return max(enumerate(ok), key=score)[1]

    def _commons_file(self, name: str) -> dict | None:
        name = name.strip().strip('"')
        if not name.lower().startswith("file:"):
            name = "File:" + name
        res = self._commons_query({"titles": name})
        if not res:
            return None
        c = res[0]
        if not c.get("url"):
            return None
        if not self._license_ok(c["license"]):
            print(f"  ! licenza non accettata per {name}: {c['license']}")
            return None
        return c

    def _commons_search(self, q: str, landscape: bool) -> dict | None:
        words = q.split()
        # se la ricerca è troppo specifica, la allarga togliendo l'ultima parola
        while words:
            res = self._commons_query({
                "generator": "search", "gsrsearch": f"{' '.join(words)} filetype:bitmap",
                "gsrnamespace": 6, "gsrlimit": 30,
            })
            pick = self._pick(res, landscape)
            if pick:
                if len(words) < len(q.split()):
                    print(f"  ricerca allargata: '{q}' → '{' '.join(words)}'")
                return pick
            if len(words) <= 2:
                break
            words = words[:-1]
        return None

    # ------------------------------------------------------------------ nasa
    def _nasa_search(self, q: str, landscape: bool) -> dict | None:
        r = self.s.get(NASA_API, params={"q": q, "media_type": "image"}, timeout=60)
        r.raise_for_status()
        items = r.json().get("collection", {}).get("items", [])[:25]
        for it in items:
            data = (it.get("data") or [{}])[0]
            nasa_id = data.get("nasa_id", "")
            try:
                assets = self.s.get(it["href"], timeout=60).json()
            except Exception:
                continue
            urls = [u for u in assets if isinstance(u, str) and u.lower().endswith((".jpg", ".jpeg", ".png"))]
            pick = next((u for u in urls if "~orig" in u), None) or next((u for u in urls if "~large" in u), None)
            if not pick:
                continue
            pick = pick.replace("http://", "https://")
            if pick in self.used:
                continue
            return {
                "title": data.get("title", nasa_id), "url": pick,
                "page": f"https://images.nasa.gov/details/{nasa_id}",
                "license": "Public domain (NASA)", "attr_req": False,
                "artist": data.get("center", "NASA"),
            }
        return None

    # ------------------------------------------------------------- fallback
    def _placeholder(self, ref: str, landscape: bool) -> str:
        w, h = (2400, 1350) if landscape else (1350, 2400)
        key = hashlib.sha1(ref.encode()).hexdigest()[:12]
        dest = self.cache / f"placeholder_{key}.jpg"
        if dest.exists():
            return str(dest)
        seed = int(key[:6], 16)
        c1 = (20 + seed % 40, 25 + (seed >> 4) % 40, 45 + (seed >> 8) % 50)
        c2 = (8, 10, 18)
        im = Image.new("RGB", (w, h), c2)
        d = ImageDraw.Draw(im)
        for y in range(h):
            t = y / h
            d.line([(0, y), (w, y)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
        # qualche "stella" per non avere un fondo piatto
        import random
        rnd = random.Random(seed)
        for _ in range(260):
            x, y, r = rnd.randrange(w), rnd.randrange(h), rnd.choice([1, 1, 2])
            v = rnd.randrange(120, 230)
            d.ellipse([x, y, x + r, y + r], fill=(v, v, v))
        im.save(dest, quality=92)
        return str(dest)

    # ------------------------------------------------------------------ api
    def resolve(self, ref: str, ep_dir: Path, landscape: bool = True) -> ImageAsset:
        kind, _, value = ref.partition(":")
        kind = kind.strip().lower()
        value = value.strip()
        if kind == "local":
            p = (ep_dir / value).resolve()
            if p.exists():
                return ImageAsset(ref, str(p), title=p.name, license="own work (channel)")
            print(f"  ! file locale mancante: {value}")
            return ImageAsset(ref, self._placeholder(ref, landscape), fallback=True)
        if self.offline:
            return ImageAsset(ref, self._placeholder(ref, landscape), fallback=True,
                              title="(offline placeholder)")
        found = None
        try:
            if kind == "commons":
                found = self._commons_file(value)
            elif kind == "search":
                found = self._commons_search(value, landscape)
            elif kind == "nasa":
                found = self._nasa_search(value, landscape)
                if not found:
                    found = self._commons_search(value, landscape)
            else:
                found = self._commons_search(ref, landscape)
        except Exception as e:  # rete, API
            print(f"  ! errore cercando '{ref}': {e}")
        if found:
            ext = ".png" if found["url"].lower().endswith(".png") else ".jpg"
            path = self._download(found["url"], ext)
            if path:
                self.used.add(found["url"])
                return ImageAsset(
                    ref, path, source_url=found["url"], page_url=found.get("page", ""),
                    title=found.get("title", ""), artist=found.get("artist", ""),
                    license=found.get("license", ""),
                    attribution_required=bool(found.get("attr_req")) or not self._is_pd(found.get("license", "")),
                )
        print(f"  ! nessuna immagine per '{ref}': uso un fondo neutro")
        return ImageAsset(ref, self._placeholder(ref, landscape), fallback=True)


def credits_text(assets: list[ImageAsset]) -> str:
    """Crediti compatti: le opere con attribuzione obbligatoria una per riga."""
    seen = set()
    lines = []
    for a in assets:
        if a.fallback or not a.attribution_required or a.page_url in seen:
            continue
        seen.add(a.page_url)
        title = re.sub(r"^File:", "", a.title).rsplit(".", 1)[0]
        artist = (a.artist or "Unknown author")[:80]
        lines.append(f"• {title} — {artist}, {a.license} — {a.page_url}")
    return "\n".join(lines)


def save_manifest(assets: list[ImageAsset], path: Path) -> None:
    path.write_text(json.dumps([asdict(a) for a in assets], indent=2, ensure_ascii=False), encoding="utf-8")
