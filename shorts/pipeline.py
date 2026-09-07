from __future__ import annotations

import datetime as dt
import json
import traceback
from dataclasses import dataclass
from pathlib import Path

from .audio_assets import ensure_audio_assets
from .compose import Overlay, Sfx, compose
from .video_gen import merge_short_segments, speaker_segments
from .config import Settings
from .overlay import render_subtitle_words, render_title, render_title_popin, resolve_font
from .providers import Providers
from .script_model import Script, slugify
from .timing import build_cues, total_duration
from .tts import synthesize_lines


@dataclass
class RunPaths:
    run_dir: Path

    @property
    def script_json(self) -> Path: return self.run_dir / "script.json"
    @property
    def scene_png(self) -> Path: return self.run_dir / "scene.png"
    @property
    def motion_mp4(self) -> Path: return self.run_dir / "motion.mp4"
    @property
    def title_png(self) -> Path: return self.run_dir / "title.png"
    @property
    def final_mp4(self) -> Path: return self.run_dir / "final.mp4"
    @property
    def meta_txt(self) -> Path: return self.run_dir / "meta.txt"
    @property
    def manifest_json(self) -> Path: return self.run_dir / "manifest.json"

    def line_mp3(self, i: int) -> Path: return self.run_dir / f"line_{i:02d}.mp3"
    def subtitle_png(self, i: int, k: int = 0) -> Path: return self.run_dir / f"sub_{i:02d}_{k:02d}.png"


class Manifest:
    """실행 폴더의 단계 상태/배포 결과 기록. 재개(resume)의 근거."""

    def __init__(self, path: Path, data: dict | None = None):
        self.path, self.data = Path(path), data or {"steps": {}, "publish": {}}

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        p = Path(path)
        return cls(p, json.loads(p.read_text("utf-8"))) if p.exists() else cls(p)

    def mark(self, step: str, status: str, **extra) -> None:
        self.data["steps"][step] = {"status": status, "at": dt.datetime.now().isoformat(timespec="seconds"), **extra}
        self.save()

    def done(self, step: str) -> bool:
        return self.data["steps"].get(step, {}).get("status") == "done"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), "utf-8")


def make_run_dir(output_dir: str | Path, title: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    p = Path(output_dir) / f"{stamp}_{slugify(title)}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def find_bgm(assets_dir: str | Path) -> Path | None:
    folder = Path(assets_dir) / "bgm"
    if not folder.exists():
        return None
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".mp3", ".m4a", ".wav"))
    return files[0] if files else None


def write_meta(script: Script, path: Path) -> None:
    tags = " ".join(script.hashtags)
    text = (f"{script.title} #Shorts\n\n"
            f"{script.character}\n{script.topic}\n\n{tags}\n\n"
            "---\n" + "\n".join(f"{l.speaker}: {l.text}" for l in script.lines) + "\n")
    path.write_text(text, "utf-8")


def plan_subtitle_overlays(cues: list, paths: RunPaths) -> list[list[Overlay]]:
    """줄마다 어절이 하나씩 드러나는 오버레이 목록. k번째 PNG 는 k개 어절이 보이며 k번째 어절 시작~다음 어절 시작 동안 표시."""
    plan: list[list[Overlay]] = []
    for i, cue in enumerate(cues):
        words = cue.words or []
        if not words:
            plan.append([Overlay(paths.subtitle_png(i, 1), cue.start, cue.end)])
            continue
        group = []
        for k, w in enumerate(words, start=1):
            end = words[k].start if k < len(words) else cue.end
            group.append(Overlay(paths.subtitle_png(i, k), w.start, max(end, w.start + 0.05)))
        plan.append(group)
    return plan


def _step(manifest: Manifest, name: str, fn) -> None:
    if manifest.done(name):
        print(f"  [skip] {name}")
        return
    print(f"  [run ] {name}")
    try:
        fn()
        manifest.mark(name, "done")
    except Exception as e:
        manifest.mark(name, "failed", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-2000:])
        raise


def _load_or_generate_script(settings: Settings, providers: Providers, topic: str, run_dir: Path | None):
    if run_dir is not None:
        paths = RunPaths(Path(run_dir))
        manifest = Manifest.load(paths.manifest_json)
        if paths.script_json.exists():
            script = Script.from_dict(json.loads(paths.script_json.read_text("utf-8")))
            return script, paths, manifest
        script = providers.script.generate(topic)
    else:
        script = providers.script.generate(topic)
        paths = RunPaths(make_run_dir(settings.output_dir, script.title))
        manifest = Manifest.load(paths.manifest_json)
    paths.script_json.write_text(json.dumps(script.to_dict(), ensure_ascii=False, indent=2), "utf-8")
    manifest.mark("script", "done", title=script.title)
    return script, paths, manifest


def run_pipeline(settings: Settings, providers: Providers, topic: str, *, run_dir: Path | None = None,
                 publish: tuple[str, ...] = ()) -> RunPaths:
    """대본 → 이미지 → 음성/타이밍 → 모션 → 오버레이 → 합성 → 메타 → (배포)."""
    script, paths, manifest = _load_or_generate_script(settings, providers, topic, run_dir)
    print(f"run dir: {paths.run_dir}")

    _step(manifest, "image", lambda: providers.image.generate(script.scene_prompt, paths.scene_png))

    utts = synthesize_lines(script, providers.tts, paths.line_mp3)
    manifest.mark("tts", "done", lines=len(utts))
    cues = build_cues([u.duration for u in utts], [u.text for u in utts], [u.speaker for u in utts],
                      words=[u.words for u in utts])
    total = total_duration(cues)

    _step(manifest, "motion",
          lambda: providers.video.generate(paths.scene_png, script.scene_prompt, total, paths.motion_mp4, cues=cues))

    font = resolve_font(settings.font_path)

    overlays = plan_subtitle_overlays(cues, paths)

    def _overlays() -> None:
        render_title(script.title, paths.title_png, font)
        render_title_popin(paths.title_png, paths.run_dir)
        for cue, group in zip(cues, overlays):
            words = [w.text for w in cue.words] or [cue.text]
            for k, ov in enumerate(group, start=1):
                render_subtitle_words(words, k, ov.png, font, punch=cue.punch)

    _step(manifest, "overlays", _overlays)
    punch = next(((c.start, total) for c in cues if c.punch), None)
    audio = ensure_audio_assets(settings.assets_dir)
    cuts = [s for s, _, _ in merge_short_segments(speaker_segments(cues, total))][1:]
    sfx = [Sfx(audio["pop"], t) for t in cuts]
    if punch:
        sfx.append(Sfx(audio["ding"], max(0.0, punch[0] - 0.15)))
    pop_frames = sorted(paths.run_dir.glob("title_pop_*.png"))
    title_frames = [Overlay(p, round(i * 0.08, 3), round((i + 1) * 0.08, 3)) for i, p in enumerate(pop_frames)]
    _step(manifest, "compose", lambda: compose(
        video=paths.motion_mp4, title_png=paths.title_png,
        overlays=[ov for group in overlays for ov in group], cues=cues, utterances=utts,
        bgm=audio["bgm"], total=total, out_path=paths.final_mp4, punch=punch, sfx=sfx,
        title_frames=title_frames))

    write_meta(script, paths.meta_txt)
    manifest.mark("meta", "done", duration=total)

    if publish:
        from .publish import publish_all
        publish_all(settings, script, paths.final_mp4, publish, manifest)
    print(f"완료: {paths.final_mp4}  ({total:.1f}s)")
    return paths
