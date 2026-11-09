"""Montaggio con ffmpeg: video lungo 16:9, Shorts 9:16, mix audio, sottotitoli, miniature."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .spec import ROOT

FONTS = ROOT / "assets" / "fonts"


def run(cmd: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"comando fallito: {' '.join(cmd[:6])}…\n{p.stderr[-2000:]}")
    return p


def fmt_ts(sec: float, srt: bool = True) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}" if srt else f"{h}:{m:02d}:{s:02d}.{ms // 10:02d}"


def chapter_ts(sec: float) -> str:
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ------------------------------------------------------------------ immagini
def _vignette(im: Image.Image, strength: float = 0.45) -> Image.Image:
    w, h = im.size
    mask = Image.new("L", (w // 8, h // 8), 0)
    d = ImageDraw.Draw(mask)
    mw, mh = mask.size
    d.ellipse([-mw * 0.15, -mh * 0.2, mw * 1.15, mh * 1.2], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(mw / 6)).resize((w, h))
    dark = ImageEnhance.Brightness(im).enhance(1 - strength)
    return Image.composite(im, dark, mask)


def grade_landscape(src: str, dest: Path, cfg: dict) -> Path:
    v = cfg["video"]
    W, H = int(v["width"] * v["overscale"]), int(v["height"] * v["overscale"])
    im = Image.open(src)
    im = ImageOps.exif_transpose(im).convert("RGB")
    ratio = im.width / im.height
    if ratio < 1.2:
        # immagine verticale o quadrata: sfondo sfocato + immagine intera al centro
        bg = ImageOps.fit(im, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
        bg = ImageEnhance.Brightness(bg).enhance(0.55)
        fg = im.copy()
        fg.thumbnail((W, int(H * 0.94)), Image.LANCZOS)
        bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
        im = bg
    else:
        im = ImageOps.fit(im, (W, H), Image.LANCZOS, centering=(0.5, 0.45))
    im = ImageEnhance.Brightness(im).enhance(v["brightness"])
    im = ImageEnhance.Color(im).enhance(v["saturation"])
    im = _vignette(im)
    im.save(dest, quality=93)
    return dest


def grade_portrait(src: str, dest: Path, cfg: dict) -> Path:
    s = cfg["shorts"]
    W, H = int(s["width"] * s["overscale"]), int(s["height"] * s["overscale"])
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    bg = ImageOps.fit(im, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(36))
    bg = ImageEnhance.Brightness(bg).enhance(0.45)
    fg = im.copy()
    target_h = int(H * 0.62)
    fg.thumbnail((W, target_h), Image.LANCZOS)
    if fg.width < W * 0.98 and im.width / im.height > 0.75:
        fg = ImageOps.fit(im, (W, min(target_h, int(W * im.height / im.width))), Image.LANCZOS)
    y = int(H * 0.16)
    bg.paste(fg, ((W - fg.width) // 2, y))
    bg = ImageEnhance.Color(bg).enhance(0.95)
    bg.save(dest, quality=93)
    return dest


# --------------------------------------------------------------------- clip
def scene_clip(img: Path, dur: float, out: Path, cfg: dict, idx: int, portrait: bool = False) -> Path:
    if portrait:
        W, H, fps = cfg["shorts"]["width"], cfg["shorts"]["height"], cfg["video"]["fps"]
        fade = 0.25
    else:
        W, H, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
        fade = min(cfg["video"]["fade"], dur / 3)
    d = max(dur, 0.5)
    # panoramica lenta, direzione alternata
    dirs = [
        ("(iw-ow)*t/{d}", "(ih-oh)/2"),
        ("(iw-ow)*(1-t/{d})", "(ih-oh)/2"),
        ("(iw-ow)/2", "(ih-oh)*t/{d}"),
        ("(iw-ow)*t/{d}", "(ih-oh)*(1-t/{d})"),
    ]
    xe, ye = dirs[idx % len(dirs)]
    xe, ye = xe.format(d=f"{d:.3f}"), ye.format(d=f"{d:.3f}")
    vf = (f"crop={W}:{H}:x='{xe}':y='{ye}',"
          f"fade=t=in:st=0:d={fade:.2f},fade=t=out:st={max(d - fade, 0):.3f}:d={fade:.2f},format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-t", f"{d:.3f}",
         "-i", str(img), "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-preset", cfg["video"]["preset"],
         "-crf", str(cfg["video"]["crf"]), "-tune", "stillimage", "-g", str(fps * 4),
         "-f", "mpegts", str(out)])
    return out


def concat_clips(clips: list[Path], out: Path) -> Path:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    return out


def mix_audio(voice: Path, music: Path, out: Path, music_db: float, lufs: float) -> Path:
    fc = (f"[1:a]volume={music_db}dB[m];[0:a][m]amix=inputs=2:duration=first:normalize=0,"
          f"loudnorm=I={lufs}:TP=-2:LRA=11,aresample=48000")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice), "-i", str(music), "-filter_complex", fc,
         "-ac", "2", "-c:a", "aac", "-b:a", "160k", str(out)])
    return out


def mux(video: Path, audio: Path, out: Path, subs_ass: Path | None = None) -> Path:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio)]
    if subs_ass:
        cmd += ["-vf", f"ass={subs_ass}:fontsdir={FONTS}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21"]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-c:a", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-movflags", "+faststart", str(out)]
    run(cmd)
    return out


# --------------------------------------------------------------- sottotitoli
def write_srt(cues, out: Path, max_words: int = 14) -> Path:
    lines = []
    n = 1
    for c in cues:
        words = c.text.split()
        parts = [words] if len(words) <= max_words else [words[: len(words) // 2], words[len(words) // 2:]]
        total = sum(len(" ".join(p)) for p in parts)
        t0 = c.start
        for p in parts:
            frac = len(" ".join(p)) / max(total, 1)
            t1 = t0 + (c.end - c.start) * frac
            lines.append(f"{n}\n{fmt_ts(t0)} --> {fmt_ts(t1)}\n{' '.join(p)}\n")
            n += 1
            t0 = t1
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_shorts_ass(cues, out: Path, cfg: dict) -> Path:
    s = cfg["shorts"]
    W, H = s["width"], s["height"]
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{s['caption_font']},{s['caption_size']},&H00FFFFFF,&H0000D7FF,&H00101010,&H64000000,0,0,0,0,100,100,1,0,1,6,2,2,80,80,{int(H * 0.13)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for c in cues:
        words = c.text.split()
        chunks, buf = [], []
        for w in words:
            buf.append(w)
            if len(buf) >= 3 or w.endswith((",", ".", "?", "!", ";", ":")):
                chunks.append(buf)
                buf = []
        if buf:
            chunks.append(buf)
        total = sum(len(" ".join(ch)) for ch in chunks) or 1
        t0 = c.start
        for ch in chunks:
            t1 = t0 + (c.end - c.start) * len(" ".join(ch)) / total
            text = " ".join(ch).upper().replace("{", "(").replace("}", ")")
            ev.append(f"Dialogue: 0,{fmt_ts(t0, False)},{fmt_ts(t1, False)},Cap,,0,0,0,,{{\\fad(60,40)}}{text}")
            t0 = t1
    out.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")
    return out


# ----------------------------------------------------------------- miniature
def _fit_text(draw, text, font_path, max_w, max_size, min_size=40, variation=None):
    size = max_size
    while size >= min_size:
        f = ImageFont.truetype(str(font_path), size)
        if variation:
            try:
                f.set_variation_by_name(variation)
            except Exception:
                pass
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return f


def make_thumbnail(img_src: str, text: str, kicker: str, out: Path) -> Path:
    W, H = 1280, 720
    im = ImageOps.exif_transpose(Image.open(img_src)).convert("RGB")
    im = ImageOps.fit(im, (W, H), Image.LANCZOS, centering=(0.6, 0.45))
    im = ImageEnhance.Contrast(im).enhance(1.12)
    im = ImageEnhance.Color(im).enhance(1.05)
    # sfumatura scura a sinistra per il testo
    grad = Image.new("L", (W, 1))
    for x in range(W):
        grad.putpixel((x, 0), int(235 * max(0.0, 1 - x / (W * 0.72)) ** 1.4))
    grad = grad.resize((W, H))
    black = Image.new("RGB", (W, H), (6, 8, 14))
    im = Image.composite(black, im, grad)
    d = ImageDraw.Draw(im)
    font_path = FONTS / "Cinzel-Variable.ttf"
    words = text.upper().split()
    # al massimo due righe bilanciate
    if len(words) > 2:
        best = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
        lines = [" ".join(words[:best]), " ".join(words[best:])]
    else:
        lines = [" ".join(words)]
    max_w = int(W * 0.58)
    fonts = [_fit_text(d, ln, font_path, max_w, 150, variation="Black") for ln in lines]
    size = min(f.size for f in fonts)
    f = ImageFont.truetype(str(font_path), size)
    try:
        f.set_variation_by_name("Black")
    except Exception:
        pass
    line_h = int(size * 1.08)
    y = (H - line_h * len(lines)) // 2 - 10
    for ln in lines:
        d.text((64, y), ln, font=f, fill=(242, 214, 140), stroke_width=max(3, size // 26), stroke_fill=(10, 10, 14))
        y += line_h
    if kicker:
        k = ImageFont.truetype(str(font_path), 34)
        try:
            k.set_variation_by_name("Bold")
        except Exception:
            pass
        d.text((68, y + 14), kicker.upper(), font=k, fill=(225, 225, 230), stroke_width=2, stroke_fill=(10, 10, 14))
    im.save(out, quality=92)
    if out.stat().st_size > 2_000_000:  # limite YouTube 2 MB
        im.save(out.with_suffix(".jpg"), quality=85)
        out.unlink()
        out = out.with_suffix(".jpg")
    return out


# ---------------------------------------------------------------- misure QA
def probe_duration(path: Path) -> float:
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    return float(json.loads(p.stdout)["format"]["duration"])


def measure_loudness(path: Path) -> float:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-filter_complex", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr)
    return float(m[-1]) if m else float("nan")


def longest_silence(path: Path, noise_db: int = -45, min_d: float = 2.0) -> float:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_d}", "-f", "null", "-"], capture_output=True, text=True)
    # ignora il silenzio finale voluto (outro): conta solo i silenzi che finiscono prima della coda del file
    total = probe_duration(path)
    ds = [float(d) for e, d in re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", p.stderr)
          if float(e) < total - 1.0]
    return max(ds) if ds else 0.0
