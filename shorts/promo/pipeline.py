"""제품 소개 영상 파이프라인: 대본 → 나레이션 → 타임라인 → 프레임 렌더 → 소리 → (배포)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..audio_assets import ensure_audio_assets
from ..config import Settings
from ..ffmpeg_tools import probe_duration
from ..pipeline import Manifest, _step, make_run_dir
from ..script_model import Line, Script
from ..tts import TTSProvider
from .audio import mux_audio
from .fonts import find_font
from .render import render_poster, render_silent_video
from .script_gen import PromoScriptProvider
from .spec import PromoScript, plain

TAIL = 0.45  # 장면이 사라지는 데 걸리는 시간


@dataclass
class PromoPaths:
    run_dir: Path

    @property
    def script_json(self) -> Path: return self.run_dir / "promo.json"
    @property
    def timeline_json(self) -> Path: return self.run_dir / "timeline.json"
    @property
    def silent_mp4(self) -> Path: return self.run_dir / "silent.mp4"
    @property
    def final_mp4(self) -> Path: return self.run_dir / "final.mp4"
    @property
    def poster_png(self) -> Path: return self.run_dir / "poster.png"
    @property
    def meta_txt(self) -> Path: return self.run_dir / "meta.txt"
    @property
    def manifest_json(self) -> Path: return self.run_dir / "manifest.json"

    def narration_mp3(self, i: int) -> Path: return self.run_dir / f"vo_{i:02d}.mp3"


def build_timeline(script: PromoScript, durations: list[float], settings: Settings) -> dict:
    """장면마다 나레이션 길이에 맞춰 시작/길이를 정한다."""
    scenes, t = [], 0.0
    for sc, d in zip(script.scenes, durations):
        dur = max(settings.promo_min_scene, settings.promo_lead + d + sc.hold + TAIL)
        scenes.append({**sc.to_dict(), "start": round(t, 3), "dur": round(dur, 3)})
        t += dur
    return {"total": round(t, 3), "accent": script.accent, "title": script.title,
            "width": settings.promo_width, "height": settings.promo_height,
            "fps": settings.promo_fps, "scenes": scenes}


def narration_cues(timeline: dict, paths: PromoPaths, lead: float) -> list[tuple[float, Path]]:
    return [(round(s["start"] + lead, 3), paths.narration_mp3(i)) for i, s in enumerate(timeline["scenes"])]


def write_meta(script: PromoScript, timeline: dict, path: Path) -> None:
    body = "\n".join(f"{i + 1:2d}. [{s['kind']}] {plain(s['title'])}" for i, s in enumerate(timeline["scenes"]))
    path.write_text(
        f"{script.title}\n\n{script.subtitle}\n{script.topic}\n\n{' '.join(script.hashtags)}\n\n"
        f"길이 {timeline['total']:.1f}초 / {timeline['width']}x{timeline['height']} / {timeline['fps']}fps\n"
        f"---\n{body}\n", "utf-8")


def as_upload_script(script: PromoScript) -> Script:
    """배포 모듈이 쓰는 필드만 채운 어댑터."""
    return Script(topic=script.topic, title=script.title, character=script.subtitle,
                  scene_prompt="", lines=[Line("reporter", plain(s.title)) for s in script.scenes[:6]],
                  hashtags=list(script.hashtags))


def _load_or_generate(provider: PromoScriptProvider, settings: Settings, brief: str, run_dir: Path | None):
    if run_dir is not None:
        paths = PromoPaths(Path(run_dir))
        manifest = Manifest.load(paths.manifest_json)
        if paths.script_json.exists():
            return PromoScript.load(paths.script_json), paths, manifest
        script = provider.generate(brief)
    else:
        script = provider.generate(brief)
        paths = PromoPaths(make_run_dir(settings.output_dir, "promo_" + (script.title or brief)))
        manifest = Manifest.load(paths.manifest_json)
    script.save(paths.script_json)
    manifest.mark("script", "done", title=script.title, scenes=len(script.scenes))
    return script, paths, manifest


def _progress(n: int, total: int) -> None:
    pct = 100.0 * n / max(1, total)
    print(f"\r    프레임 {n}/{total} ({pct:.0f}%)", end="", flush=True)
    if n >= total:
        print()


def run_promo_pipeline(settings: Settings, tts: TTSProvider, script_provider: PromoScriptProvider, brief: str,
                       *, run_dir: Path | None = None, publish: tuple[str, ...] = ()) -> PromoPaths:
    script, paths, manifest = _load_or_generate(script_provider, settings, brief, run_dir)
    print(f"run dir: {paths.run_dir}")
    font = find_font(settings.assets_dir)
    print(f"  폰트: {font.name if font else '시스템 기본(맑은 고딕)'}")

    durations: list[float] = []
    for i, sc in enumerate(script.scenes):
        p = paths.narration_mp3(i)
        if not p.exists():
            tts.synthesize(sc.speech(), "narrator", p, index=i)
        durations.append(probe_duration(p))
    manifest.mark("narration", "done", scenes=len(durations), seconds=round(sum(durations), 1))

    timeline = build_timeline(script, durations, settings)
    paths.timeline_json.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), "utf-8")
    total = float(timeline["total"])
    print(f"  장면 {len(timeline['scenes'])}개, 길이 {total:.1f}초, "
          f"{timeline['width']}x{timeline['height']} {timeline['fps']}fps")

    _step(manifest, "frames", lambda: render_silent_video(
        timeline, paths.silent_mp4, fps=settings.promo_fps, width=settings.promo_width,
        height=settings.promo_height, channel=settings.promo_browser,
        quality=settings.promo_capture_quality, crf=settings.promo_crf, font_file=font,
        on_progress=_progress))

    audio = ensure_audio_assets(settings.assets_dir)
    _step(manifest, "audio", lambda: mux_audio(
        paths.silent_mp4, narration_cues(timeline, paths, settings.promo_lead), audio["bgm"], total,
        paths.final_mp4, bgm_gain=settings.promo_bgm_gain))

    _step(manifest, "poster", lambda: render_poster(
        timeline, paths.poster_png, at=min(1.6, total / 2), width=settings.promo_width,
        height=settings.promo_height, channel=settings.promo_browser, font_file=font))

    write_meta(script, timeline, paths.meta_txt)
    manifest.mark("meta", "done", duration=total)

    if publish:
        from ..publish import publish_all
        publish_all(settings, as_upload_script(script), paths.final_mp4, publish, manifest, shorts=False)
    print(f"완료: {paths.final_mp4}  ({total:.1f}s)")
    return paths
