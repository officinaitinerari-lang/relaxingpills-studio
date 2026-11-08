"""Costruzione completa di un episodio: immagini, voce, musica, video lungo, Shorts, miniatura, QA."""
from __future__ import annotations

import json
import math
import shutil
import time
from pathlib import Path

from . import music, render
from .images import ImageFinder, credits_text, save_manifest
from .spec import ROOT, load_config, load_episode, load_shorts, parse_script
from .tts import Narrator, narrate_script, narrate_text

BUILD = ROOT / "build"


def _log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def assemble_description(meta: dict, cfg: dict, chapters: list[tuple[float, str]], credits: str) -> str:
    parts = [meta.get("description", "").strip()]
    if len(chapters) >= 3:
        parts.append("Chapters\n" + "\n".join(f"{render.chapter_ts(t)} {title}" for t, title in chapters))
    srcs = meta.get("sources") or []
    if srcs:
        parts.append("Sources & further reading\n" + "\n".join(
            f"• {s['title']}" + (f" — {s['url']}" if s.get("url") else "") for s in srcs))
    parts.append(cfg["publish"]["footer"].strip())
    if credits:
        parts.append("Image credits (openly licensed works)\n" + credits)
    tags = meta.get("hashtags") or []
    if tags:
        parts.append(" ".join(f"#{t.lstrip('#')}" for t in tags[:3]))
    desc = "\n\n".join(p for p in parts if p)
    if len(desc) > 4900 and credits:
        # crediti troppo lunghi: rimando alla pagina dei crediti nel commento fissato
        desc = desc.replace(credits, credits[: 4900 - (len(desc) - len(credits)) - 40].rsplit("\n", 1)[0]
                            + "\n• (full list in the pinned comment)")
    return desc


def build_episode(ep_dir: Path, offline: bool = False, skip_shorts: bool = False,
                  narrator: Narrator | None = None) -> dict:
    cfg = load_config()
    meta = load_episode(ep_dir)
    slug = ep_dir.name
    out = BUILD / slug
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    report = {"slug": slug, "checks": [], "ok": True, "outputs": {}}

    def check(name: str, passed: bool, detail: str = "", fatal: bool = True):
        report["checks"].append({"name": name, "ok": bool(passed), "detail": detail, "fatal": fatal})
        if not passed and fatal:
            report["ok"] = False
        _log(f"QA {'OK ' if passed else ('KO ' if fatal else 'WARN')} {name} {detail}")

    script = parse_script(ep_dir / "script.md")
    _log(f"{slug}: {len(script.chapters)} capitoli, {len(script.scenes)} scene, {script.word_count} parole")

    # ------------------------------------------------------------ immagini
    finder = ImageFinder(cfg, BUILD / "_image_cache", offline=offline)
    scene_assets = []
    for scene in script.scenes:
        scene_assets.append([finder.resolve(ref, ep_dir, landscape=True) for ref in scene.images])
    all_assets = [a for lst in scene_assets for a in lst]
    fb = sum(a.fallback for a in all_assets) / max(len(all_assets), 1)
    _log(f"immagini: {len(all_assets)} ({fb:.0%} sostitutive)")

    # --------------------------------------------------------------- voce
    narrator = narrator or Narrator(cfg)
    voice_wav = work / "voice.wav"
    cues, bounds, chap_starts, total = narrate_script(script, cfg, voice_wav, narrator)
    _log(f"voce: {total/60:.1f} min")

    # ------------------------------------------------------------- musica
    music_wav = work / "music.wav"
    music.generate(music_wav, total, slug, meta.get("pillar", "history"))
    audio = render.mix_audio(voice_wav, music_wav, work / "audio.m4a", cfg["audio"]["music_db"], cfg["audio"]["target_lufs"])

    # -------------------------------------------------------------- video
    clips = []
    longest_img = 0.0
    k = 0
    for si, ((s0, s1), assets) in enumerate(zip(bounds, scene_assets)):
        n = len(assets)
        seg = (s1 - s0) / n
        for j, a in enumerate(assets):
            graded = render.grade_landscape(a.path, work / f"img_{si:03d}_{j}.jpg", cfg)
            clips.append(render.scene_clip(graded, seg, work / f"clip_{k:04d}.ts", cfg, k))
            longest_img = max(longest_img, seg)
            k += 1
        if si % 10 == 0:
            _log(f"video: scena {si + 1}/{len(bounds)}")
    video = render.concat_clips(clips, work / "video.ts")
    long_mp4 = render.mux(video, audio, out / f"{slug}.mp4")
    report["outputs"]["long"] = str(long_mp4)

    srt = render.write_srt(cues, out / f"{slug}.en.srt")
    report["outputs"]["srt"] = str(srt)

    chapters = [(chap_starts[c.index], c.title) for c in script.chapters if c.index in chap_starts]
    if chapters:
        chapters[0] = (0.0, chapters[0][1])
    credits = credits_text(all_assets)
    desc = assemble_description(meta, cfg, chapters, credits)
    (out / "description.txt").write_text(desc, encoding="utf-8")
    report["outputs"]["description"] = str(out / "description.txt")
    save_manifest(all_assets, out / "images.json")

    # ---------------------------------------------------------- miniatura
    th = meta.get("thumbnail") or {}
    custom = ep_dir / th.get("file", "thumbnail.png")
    if custom.exists():
        thumb = out / f"thumbnail{custom.suffix}"
        shutil.copy(custom, thumb)
        report["thumbnail_source"] = "custom"
    else:
        img = finder.resolve(th["image"], ep_dir, True) if th.get("image") else (all_assets[0] if all_assets else None)
        kicker = "History for Sleep" if meta.get("pillar") == "history" else "Science for Sleep"
        thumb = render.make_thumbnail(img.path, th.get("text", meta["title"][:24]), kicker, out / "thumbnail.png")
        report["thumbnail_source"] = "auto"
    report["outputs"]["thumbnail"] = str(thumb)

    # ----------------------------------------------------------------- QA
    q = cfg["qa"]
    dur = render.probe_duration(long_mp4)
    lo, hi = meta.get("min_minutes", q["long_min_minutes"]), meta.get("max_minutes", q["long_max_minutes"])
    check("durata video lungo", lo * 60 <= dur <= hi * 60, f"{dur/60:.1f} min (atteso {lo}-{hi})")
    check("video e audio allineati", abs(dur - total) < 3, f"video {dur:.1f}s, voce {total:.1f}s")
    lufs = render.measure_loudness(audio)
    check("volume", abs(lufs - cfg["audio"]["target_lufs"]) <= q["lufs_tolerance"], f"{lufs:.1f} LUFS")
    sil = render.longest_silence(voice_wav, -45, 3.0)
    check("pause troppo lunghe nella voce", sil <= q["max_silence_seconds"], f"max {sil:.1f}s")
    check("immagini sostitutive", fb <= cfg["images"]["max_fallback_ratio"], f"{fb:.0%}", fatal=not offline)
    check("immagine tenuta troppo a lungo", longest_img <= q["max_image_seconds"], f"max {longest_img:.0f}s", fatal=False)
    check("titolo", 10 <= len(meta["title"]) <= 100, f"{len(meta['title'])} caratteri")
    check("descrizione", len(desc) <= 5000, f"{len(desc)} caratteri")
    tags = list(dict.fromkeys((meta.get("tags") or []) + cfg["publish"]["default_tags"]))
    while len(",".join(tags)) > 480:
        tags.pop()
    report["tags"] = tags
    check("capitoli", len(chapters) >= 3, f"{len(chapters)}", fatal=False)
    report["duration_min"] = round(dur / 60, 1)
    report["words"] = script.word_count

    # ------------------------------------------------------------- Shorts
    report["shorts"] = []
    if not skip_shorts:
        for i, sh in enumerate(load_shorts(ep_dir), start=1):
            report["shorts"].append(build_short(ep_dir, sh, i, cfg, finder, narrator, out, check))

    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _log(f"{slug}: {'PRONTO' if report['ok'] else 'BLOCCATO DAI CONTROLLI'}")
    return report


def build_short(ep_dir, sh, i, cfg, finder, narrator, out, check) -> dict:
    slug = ep_dir.name
    work = out / "work" / f"short{i}"
    work.mkdir(parents=True, exist_ok=True)
    voice = work / "voice.wav"
    cues, total = narrate_text(sh["text"], cfg, voice, narrator, cfg["voice"]["speed_shorts"])
    mus = work / "music.wav"
    music.generate(mus, total, f"{slug}-short{i}", "science" if "nasa" in " ".join(sh.get("images", [])) else "history",
                   slot=12, xfade=4)
    audio = render.mix_audio(voice, mus, work / "audio.m4a", cfg["shorts"]["music_db"], cfg["shorts"]["target_lufs"])
    assets = [finder.resolve(r, ep_dir, landscape=False) for r in sh.get("images", [])] or \
             [finder.resolve("search:" + sh.get("title", slug), ep_dir, landscape=False)]
    seg = total / len(assets)
    clips = []
    for j, a in enumerate(assets):
        g = render.grade_portrait(a.path, work / f"img_{j}.jpg", cfg)
        clips.append(render.scene_clip(g, seg, work / f"clip_{j}.ts", cfg, j, portrait=True))
    video = render.concat_clips(clips, work / "video.ts")
    ass = render.write_shorts_ass(cues, work / "captions.ass", cfg)
    mp4 = render.mux(video, audio, out / f"{slug}-short{i}.mp4", subs_ass=ass)
    dur = render.probe_duration(mp4)
    q = cfg["qa"]
    check(f"durata Short {i}", q["shorts_min_seconds"] <= dur <= q["shorts_max_seconds"], f"{dur:.1f}s")
    check(f"titolo Short {i}", 5 <= len(sh["title"]) <= 100, f"{len(sh['title'])} caratteri")
    return {"index": i, "path": str(mp4), "duration": round(dur, 1), "title": sh["title"],
            "publish_at": sh.get("publish_at"), "fallback_images": sum(a.fallback for a in assets)}
