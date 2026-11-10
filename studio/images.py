"""Reperimento immagini libere: Wikimedia Commons, musei open access, NASA, file locali.

Regola del canale (10 nov 2026): ogni immagine è scelta UNA PER UNA, puntando alla massima aderenza al testo,
e deve essere di qualità. Nello script si usano solo riferimenti esatti:

  commons:File:Nome.jpg    file preciso su Wikimedia Commons (pubblico dominio, CC0, CC BY, CC BY-SA)
  met:436535               opera del Metropolitan Museum of Art (Open Access, CC0)
  aic:27992                opera dell'Art Institute of Chicago (pubblico dominio, CC0)
  cma:135382               opera del Cleveland Museum of Art (Open Access, CC0)
  nasaid:PIA21973          immagine NASA (pubblico dominio)
  local:images/nome.jpg    file nella cartella dell'episodio

I riferimenti generici (search:, nasa:) restano solo per prove manuali: il controllo li rifiuta negli episodi.
I candidati per ogni scena si trovano con studio/candidates.py (workflow "Ricerca immagini").
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
NASA_SEARCH = "https://images-api.nasa.gov/search"
NASA_ASSET = "https://images-api.nasa.gov/asset/"
MET_API = "https://collectionapi.metmuseum.org/public/collection/v1"
AIC_API = "https://api.artic.edu/api/v1/artworks"
CMA_API = "https://openaccess-api.clevelandart.org/api/artworks"

EXACT_KINDS = ("commons", "met", "aic", "cma", "nasaid", "local")

# distanza minima tra due richieste allo stesso sito (secondi): Wikimedia chiede educazione
HOST_GAP = {"commons.wikimedia.org": 1.0, "upload.wikimedia.org": 0.6}
DEFAULT_GAP = 0.25


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
    width: int = 0
    height: int = 0


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


class Sources:
    """Accesso educato alle fonti: rate limit per sito, nuovi tentativi su 429/5xx."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.s = requests.Session()
        self.s.headers["User-Agent"] = cfg["channel"]["user_agent"]
        icfg = cfg["images"]
        self.allowed = [a.lower() for a in icfg["allowed_licenses"]]
        self._last: dict[str, float] = {}

    # ------------------------------------------------------------------ http
    def get(self, url: str, params: dict | None = None, timeout: int = 60):
        host = urlparse(url).netloc
        gap = HOST_GAP.get(host, DEFAULT_GAP)
        r = None
        for attempt in range(6):
            wait = gap - (time.monotonic() - self._last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.monotonic()
            try:
                r = self.s.get(url, params=params, timeout=timeout)
            except requests.RequestException:
                time.sleep(3 * (attempt + 1))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                ra = r.headers.get("Retry-After", "")
                time.sleep(min(int(ra) if ra.isdigit() else 5 * (attempt + 1), 60))
                continue
            return r
        if r is not None:
            r.raise_for_status()
        raise requests.RequestException(f"nessuna risposta da {url}")

    def license_ok(self, lic: str) -> bool:
        l = (lic or "").lower()
        if not l or any(x in l for x in ("nonfree", "fair use", "-nd", " nd ", "-nc", " nc ")):
            return False
        return any(l.startswith(a) or a in l for a in self.allowed)

    @staticmethod
    def is_pd(lic: str) -> bool:
        l = (lic or "").lower()
        return "public domain" in l or l.startswith("pd") or "cc0" in l or "no restrictions" in l

    # --------------------------------------------------------------- commons
    def _commons_items(self, params: dict, thumb: int = 2400) -> list[dict]:
        base = {"action": "query", "format": "json", "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata", "iiurlwidth": thumb}
        base.update(params)
        r = self.get(COMMONS_API, params=base)
        r.raise_for_status()
        pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
        out = []
        for p in pages:
            ii = (p.get("imageinfo") or [{}])[0]
            if not ii:
                continue
            md = ii.get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value", "")
            out.append({
                "ref": "commons:" + p.get("title", ""), "source": "Wikimedia Commons",
                "title": re.sub(r"^File:", "", p.get("title", "")).rsplit(".", 1)[0],
                "description": _strip_html(md.get("ImageDescription", {}).get("value", ""))[:240],
                "artist": _strip_html(md.get("Artist", {}).get("value", ""))[:80],
                "date": _strip_html(md.get("DateTimeOriginal", {}).get("value", ""))[:40],
                "width": ii.get("width", 0), "height": ii.get("height", 0), "mime": ii.get("mime", ""),
                "url": ii.get("thumburl") or ii.get("url"), "thumb": None,
                "page": ii.get("descriptionurl", ""), "license": lic,
                "attr_req": not self.is_pd(lic),
            })
        return out

    def commons_exact(self, name: str) -> dict | None:
        name = name.strip().strip('"')
        if not name.lower().startswith("file:"):
            name = "File:" + name
        res = self._commons_items({"titles": name})
        return res[0] if res and res[0].get("url") else None

    def commons_search(self, q: str, limit: int = 20) -> list[dict]:
        items = self._commons_items({"generator": "search", "gsrsearch": f"{q} filetype:bitmap",
                                     "gsrnamespace": 6, "gsrlimit": limit}, thumb=2400)
        return [i for i in items if i["mime"] in ("image/jpeg", "image/png", "image/tiff", "image/webp")
                and self.license_ok(i["license"])]

    # ------------------------------------------------------------------- met
    def met_exact(self, oid: str) -> dict | None:
        r = self.get(f"{MET_API}/objects/{oid}")
        if r.status_code != 200:
            return None
        o = r.json()
        if not o.get("isPublicDomain") or not o.get("primaryImage"):
            return None
        return {
            "ref": f"met:{o['objectID']}", "source": "The Met (Open Access)",
            "title": o.get("title", "")[:120], "artist": o.get("artistDisplayName", "")[:80],
            "date": o.get("objectDate", ""), "description": " · ".join(x for x in (o.get("culture"), o.get("medium"), o.get("department")) if x)[:240],
            "url": o["primaryImage"], "thumb": o.get("primaryImageSmall"),
            "width": 0, "height": 0, "page": o.get("objectURL", ""),
            "license": "Public domain (The Met Open Access, CC0)", "attr_req": False,
        }

    def met_search(self, q: str, limit: int = 10) -> list[dict]:
        r = self.get(f"{MET_API}/search", params={"q": q, "hasImages": "true"})
        if r.status_code != 200:
            print(f"  met: HTTP {r.status_code}")
            return []
        ids = (r.json().get("objectIDs") or [])[:limit * 3]
        out = []
        for oid in ids:
            it = self.met_exact(str(oid))
            if it:
                out.append(it)
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------------- aic
    @staticmethod
    def _aic_item(d: dict) -> dict | None:
        if not d.get("is_public_domain") or not d.get("image_id"):
            return None
        th = d.get("thumbnail") or {}
        w = th.get("width") or 0
        h = th.get("height") or 0
        return {
            "ref": f"aic:{d['id']}", "source": "Art Institute of Chicago",
            "title": (d.get("title") or "")[:120], "artist": (d.get("artist_title") or "")[:80],
            "date": d.get("date_display") or "", "description": _strip_html(th.get("alt_text") or "")[:240],
            "url": f"https://www.artic.edu/iiif/2/{d['image_id']}/full/2400,/0/default.jpg",
            "thumb": f"https://www.artic.edu/iiif/2/{d['image_id']}/full/400,/0/default.jpg",
            "width": w, "height": h, "page": f"https://www.artic.edu/artworks/{d['id']}",
            "license": "Public domain (Art Institute of Chicago, CC0)", "attr_req": False,
        }

    AIC_FIELDS = "id,title,image_id,artist_title,date_display,is_public_domain,thumbnail"

    def aic_exact(self, aid: str) -> dict | None:
        r = self.get(f"{AIC_API}/{aid}", params={"fields": self.AIC_FIELDS})
        return self._aic_item(r.json().get("data", {})) if r.status_code == 200 else None

    def aic_search(self, q: str, limit: int = 10) -> list[dict]:
        r = self.get(f"{AIC_API}/search", params={"q": q, "limit": limit * 3, "fields": self.AIC_FIELDS})
        if r.status_code != 200:
            print(f"  aic: HTTP {r.status_code}")
            return []
        return [x for x in (self._aic_item(d) for d in r.json().get("data", [])) if x][:limit]

    # ------------------------------------------------------------------- cma
    @staticmethod
    def _cma_item(d: dict) -> dict | None:
        if (d.get("share_license_status") or "").upper() != "CC0":
            return None
        imgs = d.get("images") or {}
        big = imgs.get("print") or imgs.get("full") or imgs.get("web") or {}
        web = imgs.get("web") or big
        if not big.get("url"):
            return None
        creators = ", ".join(c.get("description", "") for c in (d.get("creators") or []))
        return {
            "ref": f"cma:{d['id']}", "source": "Cleveland Museum of Art (Open Access)",
            "title": (d.get("title") or "")[:120], "artist": creators[:80], "date": d.get("creation_date") or "",
            "description": _strip_html(d.get("description") or "")[:240],
            "url": big["url"], "thumb": web.get("url"),
            "width": int(big.get("width") or 0), "height": int(big.get("height") or 0),
            "page": d.get("url", ""), "license": "Public domain (Cleveland Museum of Art, CC0)", "attr_req": False,
        }

    def cma_exact(self, cid: str) -> dict | None:
        r = self.get(f"{CMA_API}/{cid}")
        return self._cma_item(r.json().get("data", {})) if r.status_code == 200 else None

    def cma_search(self, q: str, limit: int = 10) -> list[dict]:
        r = self.get(CMA_API, params={"q": q, "has_image": 1, "cc0": 1, "limit": limit})
        if r.status_code != 200:
            print(f"  cma: HTTP {r.status_code}")
            return []
        return [x for x in (self._cma_item(d) for d in r.json().get("data", [])) if x]

    # ------------------------------------------------------------------ nasa
    def nasa_exact(self, nasa_id: str) -> dict | None:
        r = self.get(NASA_ASSET + nasa_id)
        if r.status_code != 200:
            return None
        hrefs = [i.get("href", "") for i in r.json().get("collection", {}).get("items", [])]
        imgs = [h for h in hrefs if h.lower().endswith((".jpg", ".jpeg", ".png"))]
        pick = next((h for h in imgs if "~orig" in h), None) or next((h for h in imgs if "~large" in h), None)
        if not pick:
            return None
        meta = self.get(NASA_SEARCH, params={"nasa_id": nasa_id})
        data = {}
        if meta.status_code == 200:
            items = meta.json().get("collection", {}).get("items", [])
            data = (items[0].get("data") or [{}])[0] if items else {}
        thumb = next((h for h in imgs if "~thumb" in h or "~small" in h), None)
        return {
            "ref": f"nasaid:{nasa_id}", "source": "NASA",
            "title": data.get("title", nasa_id)[:120], "artist": data.get("center", "NASA"),
            "date": (data.get("date_created") or "")[:10], "description": _strip_html(data.get("description", ""))[:240],
            "url": pick.replace("http://", "https://"), "thumb": (thumb or pick).replace("http://", "https://"),
            "width": 0, "height": 0, "page": f"https://images.nasa.gov/details/{nasa_id}",
            "license": "Public domain (NASA)", "attr_req": False,
        }

    def nasa_search(self, q: str, limit: int = 8) -> list[dict]:
        r = self.get(NASA_SEARCH, params={"q": q, "media_type": "image"})
        if r.status_code != 200:
            return []
        out = []
        for it in r.json().get("collection", {}).get("items", [])[:limit]:
            d = (it.get("data") or [{}])[0]
            links = it.get("links") or [{}]
            out.append({
                "ref": f"nasaid:{d.get('nasa_id')}", "source": "NASA", "title": d.get("title", "")[:120],
                "artist": d.get("center", "NASA"), "date": (d.get("date_created") or "")[:10],
                "description": _strip_html(d.get("description", ""))[:240],
                "url": None, "thumb": (links[0].get("href") or "").replace("http://", "https://"),
                "width": 0, "height": 0, "page": f"https://images.nasa.gov/details/{d.get('nasa_id')}",
                "license": "Public domain (NASA)", "attr_req": False,
            })
        return out

    # ---------------------------------------------------------------- unico
    def exact(self, ref: str) -> dict | None:
        kind, _, value = ref.partition(":")
        kind, value = kind.strip().lower(), value.strip()
        fn = {"commons": self.commons_exact, "met": self.met_exact, "aic": self.aic_exact,
              "cma": self.cma_exact, "nasaid": self.nasa_exact}.get(kind)
        return fn(value) if fn else None


class ImageFinder:
    """Usato dal montaggio: risolve i riferimenti dello script e scarica le immagini in alta qualità."""

    def __init__(self, cfg: dict, cache_dir: Path, offline: bool = False):
        self.cfg = cfg
        self.cache = cache_dir
        self.cache.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.src = Sources(cfg)
        self.min_width = cfg["images"].get("min_width_exact", 1280)
        self.used: set[str] = set()

    def _download(self, url: str, ext: str = ".jpg") -> str | None:
        key = hashlib.sha1(url.encode()).hexdigest()[:16]
        dest = self.cache / f"{key}{ext}"
        if dest.exists() and dest.stat().st_size > 1000:
            return str(dest)
        try:
            r = self.src.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                dest.write_bytes(r.content)
                with Image.open(dest) as im:
                    im.verify()
                return str(dest)
        except Exception as e:
            print(f"  ! download fallito {url[:90]}: {e}")
        return None

    def _placeholder(self, ref: str, landscape: bool) -> str:
        w, h = (2400, 1350) if landscape else (1350, 2400)
        key = hashlib.sha1(ref.encode()).hexdigest()[:12]
        dest = self.cache / f"placeholder_{key}.jpg"
        if dest.exists():
            return str(dest)
        im = Image.new("RGB", (w, h), (10, 12, 20))
        d = ImageDraw.Draw(im)
        for y in range(h):
            t = y / h
            d.line([(0, y), (w, y)], fill=(int(30 * (1 - t) + 10 * t), int(34 * (1 - t) + 12 * t), int(55 * (1 - t) + 20 * t)))
        im.save(dest, quality=92)
        return str(dest)

    def resolve(self, ref: str, ep_dir: Path, landscape: bool = True) -> ImageAsset:
        kind, _, value = ref.partition(":")
        kind = kind.strip().lower()
        value = value.strip()
        if kind == "local":
            p = (ep_dir / value).resolve()
            if p.exists():
                with Image.open(p) as im:
                    w, h = im.size
                return ImageAsset(ref, str(p), title=p.name, license="own work (channel)", width=w, height=h)
            print(f"  ! file locale mancante: {value}")
            return ImageAsset(ref, self._placeholder(ref, landscape), fallback=True)
        if self.offline:
            return ImageAsset(ref, self._placeholder(ref, landscape), fallback=True, title="(offline)")
        item = None
        try:
            if kind in ("commons", "met", "aic", "cma", "nasaid"):
                item = self.src.exact(ref)
                if item and kind == "commons" and not self.src.license_ok(item["license"]):
                    print(f"  ! licenza non accettata per {ref}: {item['license']}")
                    item = None
            elif kind == "search":  # solo prove manuali
                res = self.src.commons_search(value)
                item = next((i for i in res if i["width"] >= self.min_width and i["url"] not in self.used), None)
            elif kind == "nasa":
                res = self.src.nasa_search(value, limit=3)
                item = self.src.nasa_exact(res[0]["ref"].split(":", 1)[1]) if res else None
        except Exception as e:
            print(f"  ! errore con '{ref}': {e}")
        if not item:
            print(f"  ! immagine non trovata: {ref}")
            return ImageAsset(ref, self._placeholder(ref, landscape), fallback=True)
        ext = ".png" if str(item["url"]).lower().endswith(".png") else ".jpg"
        path = self._download(item["url"], ext)
        if not path:
            return ImageAsset(ref, self._placeholder(ref, landscape), fallback=True)
        with Image.open(path) as im:
            w, h = im.size
        if max(w, h) < self.min_width:
            print(f"  ! risoluzione troppo bassa ({w}x{h}) per {ref}")
            return ImageAsset(ref, self._placeholder(ref, landscape), fallback=True, width=w, height=h)
        self.used.add(item["url"])
        return ImageAsset(ref, path, source_url=item["url"], page_url=item.get("page", ""),
                          title=item.get("title", ""), artist=item.get("artist", ""), license=item.get("license", ""),
                          attribution_required=bool(item.get("attr_req")), width=w, height=h)


def credits_text(assets: list[ImageAsset]) -> str:
    """Crediti: le opere con attribuzione obbligatoria una per riga, i musei CC0 in una riga di ringraziamento."""
    seen, lines, museums = set(), [], set()
    for a in assets:
        if a.fallback or a.page_url in seen:
            continue
        seen.add(a.page_url)
        if a.attribution_required:
            title = re.sub(r"^File:", "", a.title).rsplit(".", 1)[0]
            lines.append(f"• {title} — {(a.artist or 'Unknown author')[:80]}, {a.license} — {a.page_url}")
        elif "Met" in a.license:
            museums.add("The Metropolitan Museum of Art")
        elif "Chicago" in a.license:
            museums.add("Art Institute of Chicago")
        elif "Cleveland" in a.license:
            museums.add("Cleveland Museum of Art")
        elif "NASA" in a.license:
            museums.add("NASA")
    out = "\n".join(lines)
    if museums:
        out = (out + "\n" if out else "") + "Open-access images courtesy of " + ", ".join(sorted(museums)) + "."
    return out


def save_manifest(assets: list[ImageAsset], path: Path) -> None:
    path.write_text(json.dumps([asdict(a) for a in assets], indent=2, ensure_ascii=False), encoding="utf-8")
