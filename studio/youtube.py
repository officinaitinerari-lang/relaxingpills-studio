"""YouTube Data API: caricamento programmato, miniatura, sottotitoli, playlist, manutenzione canale.

Credenziali dai secret del repository: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def has_credentials() -> bool:
    return all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def to_publish_at(local: str | None, tz: str, min_hours_ahead: float) -> str | None:
    """'2026-12-01T02:00' (ora di Roma) → RFC3339 UTC; se è troppo vicina, spostata in avanti."""
    if not local:
        return None
    dt = datetime.fromisoformat(str(local))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz))
    earliest = datetime.now(timezone.utc) + timedelta(hours=min_hours_ahead)
    if dt.astimezone(timezone.utc) < earliest:
        print(f"  ! data di uscita {local} troppo vicina o passata: sposto a {earliest:%Y-%m-%d %H:%M} UTC")
        dt = earliest
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _resumable(request, label: str):
    from googleapiclient.errors import HttpError
    response = None
    retries = 0
    last = -1
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                if pct // 10 != last // 10:
                    print(f"  caricamento {label}: {pct}%", flush=True)
                    last = pct
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 8:
                retries += 1
                time.sleep(min(2 ** retries, 60))
                continue
            raise
        except (ConnectionError, TimeoutError, OSError):
            if retries < 8:
                retries += 1
                time.sleep(min(2 ** retries, 60))
                continue
            raise
    return response


def upload_video(yt, path: Path, title: str, description: str, tags: list[str], cfg: dict,
                 publish_at_local: str | None, localizations: dict | None = None) -> dict:
    from googleapiclient.http import MediaFileUpload
    p = cfg["publish"]
    publish_at = to_publish_at(publish_at_local, p["timezone"], p["min_hours_ahead"])
    status = {
        "privacyStatus": "private",
        "selfDeclaredMadeForKids": bool(p["made_for_kids"]),
        "containsSyntheticMedia": bool(p["contains_synthetic_media"]),
        "embeddable": True,
    }
    if publish_at:
        status["publishAt"] = publish_at
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": p["category_id"],
            "defaultLanguage": cfg["channel"]["language"],
            "defaultAudioLanguage": cfg["channel"]["language"],
        },
        "status": status,
    }
    part = "snippet,status"
    if localizations:
        # titoli e descrizioni tradotti: il video compare nelle ricerche in altre lingue
        body["localizations"] = {
            lang: {"title": v["title"][:100], "description": v.get("description", "")[:5000]}
            for lang, v in localizations.items() if v.get("title")
        }
        part += ",localizations"
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=16 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part=part, body=body, media_body=media, notifySubscribers=True)
    res = _resumable(req, path.name)
    return {"video_id": res["id"], "publish_at": publish_at,
            "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "upload_status": res.get("status", {}).get("uploadStatus"),
            "privacy": res.get("status", {}).get("privacyStatus")}


def set_thumbnail(yt, video_id: str, path: Path) -> str:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    mt = "image/png" if path.suffix == ".png" else "image/jpeg"
    try:
        yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(path), mimetype=mt)).execute()
        return "ok"
    except HttpError as e:
        # 403 = canale non verificato col telefono (youtube.com/verify)
        return f"errore {e.resp.status}: {e._get_reason()[:120]}"


def add_captions(yt, video_id: str, srt: Path, lang: str = "en") -> str:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    try:
        yt.captions().insert(
            part="snippet",
            body={"snippet": {"videoId": video_id, "language": lang, "name": "English", "isDraft": False}},
            media_body=MediaFileUpload(str(srt), mimetype="application/octet-stream"),
        ).execute()
        return "ok"
    except HttpError as e:
        return f"errore {e.resp.status}: {e._get_reason()[:120]}"


def add_to_playlist(yt, playlist_id: str, video_id: str) -> str:
    from googleapiclient.errors import HttpError
    if not playlist_id:
        return "nessuna playlist"
    try:
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
        return "ok"
    except HttpError as e:
        return f"errore {e.resp.status}: {e._get_reason()[:120]}"


# ------------------------------------------------------------ manutenzione
def channel_info(yt) -> dict:
    r = yt.channels().list(part="snippet,statistics,brandingSettings,status", mine=True).execute()
    return (r.get("items") or [{}])[0]


def set_privacy(yt, video_id: str, privacy: str) -> str:
    from googleapiclient.errors import HttpError
    try:
        cur = yt.videos().list(part="status", id=video_id).execute()["items"][0]["status"]
        cur["privacyStatus"] = privacy
        cur.pop("publishAt", None)
        yt.videos().update(part="status", body={"id": video_id, "status": cur}).execute()
        return "ok"
    except (HttpError, IndexError, KeyError) as e:
        return f"errore: {e}"


def ensure_playlist(yt, title: str, description: str) -> str:
    page = None
    while True:
        r = yt.playlists().list(part="snippet", mine=True, maxResults=50, pageToken=page).execute()
        for it in r.get("items", []):
            if it["snippet"]["title"] == title:
                return it["id"]
        page = r.get("nextPageToken")
        if not page:
            break
    r = yt.playlists().insert(part="snippet,status", body={
        "snippet": {"title": title, "description": description, "defaultLanguage": "en"},
        "status": {"privacyStatus": "public"}}).execute()
    return r["id"]


def update_channel_branding(yt, description: str, keywords: str) -> str:
    ch = channel_info(yt)
    bs = ch.get("brandingSettings", {})
    bs.setdefault("channel", {})
    bs["channel"]["description"] = description
    bs["channel"]["keywords"] = keywords
    bs["channel"]["defaultLanguage"] = "en"
    body = {"channel": bs["channel"]}
    if "watch" in bs:
        body["watch"] = bs["watch"]
    yt.channels().update(part="brandingSettings", body={"id": ch["id"], "brandingSettings": body}).execute()
    return "ok"
