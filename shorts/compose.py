from __future__ import annotations

from pathlib import Path

from .ffmpeg_tools import run_ffmpeg
from .timing import Cue
from .tts import Utterance

TITLE_Y = 130          # 상단 제목 y
SUBTITLE_BOTTOM = 260  # 하단 자막 아래 여백
BGM_VOLUME = 0.12
_AFMT = "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"


def build_compose_command(*, video: Path, title_png: Path, subtitle_pngs: list[Path], cues: list[Cue],
                          utterances: list[Utterance], bgm: Path | None, total: float, out_path: Path) -> list[str]:
    """모션 영상 + 제목/자막 PNG 오버레이 + 대사 음성 배치 + BGM 을 한 번의 ffmpeg 호출로 합성."""
    inputs: list[str] = ["-i", str(video), "-i", str(title_png)]
    for p in subtitle_pngs:
        inputs += ["-i", str(p)]
    audio_base = 2 + len(subtitle_pngs)
    for u in utterances:
        inputs += ["-i", str(u.path)]
    bgm_idx = None
    if bgm is not None:
        bgm_idx = audio_base + len(utterances)
        inputs += ["-stream_loop", "-1", "-i", str(bgm)]

    f = [f"[0:v]trim=0:{total:.3f},setpts=PTS-STARTPTS,scale=1080:1920,format=yuv420p[v0]",
         f"[v0][1:v]overlay=(W-w)/2:{TITLE_Y}[v1]"]
    cur = "v1"
    for i, (png, cue) in enumerate(zip(subtitle_pngs, cues)):
        nxt = f"v{i + 2}"
        f.append(f"[{cur}][{2 + i}:v]overlay=(W-w)/2:H-h-{SUBTITLE_BOTTOM}"
                 f":enable='between(t,{cue.start:g},{cue.end:g})'[{nxt}]")
        cur = nxt
    f.append(f"[{cur}]null[vout]")

    labels = []
    for k, (u, cue) in enumerate(zip(utterances, cues)):
        ms = int(round(cue.start * 1000))
        f.append(f"[{audio_base + k}:a]{_AFMT},adelay={ms}|{ms}[a{k}]")
        labels.append(f"[a{k}]")
    if bgm_idx is not None:
        f.append(f"[{bgm_idx}:a]{_AFMT},volume={BGM_VOLUME},atrim=0:{total:.3f}[abgm]")
        labels.append("[abgm]")
    n = len(labels)
    if n == 1:
        f.append(f"{labels[0]}apad,atrim=0:{total:.3f}[aout]")
    else:
        f.append(f"{''.join(labels)}amix=inputs={n}:normalize=0:dropout_transition=0,apad,atrim=0:{total:.3f}[aout]")

    return [*inputs, "-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out_path)]


def compose(**kwargs) -> Path:
    out = Path(kwargs["out_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(build_compose_command(**kwargs))
    return out
