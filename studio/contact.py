"""Foglio provini: miniatura + 8 fotogrammi del video lungo + un fotogramma per Short."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from .render import probe_duration


def frame(video: Path, t: float, w: int) -> Image.Image:
    out = video.parent / f"_f_{int(t*10)}.jpg"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                    "-vf", f"scale={w}:-2", str(out)], check=True)
    im = Image.open(out).convert("RGB")
    out.unlink()
    return im


def contact_sheet(build_dir: Path, dest: Path) -> Path:
    slug = build_dir.name
    long_mp4 = build_dir / f"{slug}.mp4"
    tiles = []
    thumb = next(iter(sorted(build_dir.glob("thumbnail.*"))), None)
    if thumb:
        tiles.append(Image.open(thumb).convert("RGB").resize((480, 270)))
    if long_mp4.exists():
        d = probe_duration(long_mp4)
        for k in range(1, 9):
            tiles.append(frame(long_mp4, d * k / 9, 480))
    shorts = [frame(p, min(6.0, probe_duration(p) / 2), 152) for p in sorted(build_dir.glob(f"{slug}-short*.mp4"))]
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    W = cols * 488 + 8 + (len(shorts) and 160 + 8)
    H = max(rows * 278 + 8, 278 * len(shorts) + 8 if shorts else 0, 286)
    sheet = Image.new("RGB", (W, H), (240, 240, 240))
    for i, t in enumerate(tiles):
        sheet.paste(t, (8 + (i % cols) * 488, 8 + (i // cols) * 278))
    for j, s in enumerate(shorts):
        sheet.paste(s, (cols * 488 + 8, 8 + j * 278))
    ImageDraw.Draw(sheet).text((12, H - 16), slug, fill=(40, 40, 40))
    sheet.save(dest, quality=85)
    return dest


if __name__ == "__main__":
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for d in sorted(Path(sys.argv[1]).iterdir()):
        if d.is_dir() and not d.name.startswith("_image") and (d / f"{d.name}.mp4").exists():
            print(contact_sheet(d, out / f"{d.name}-provini.jpg"))
