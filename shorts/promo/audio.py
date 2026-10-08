"""나레이션 + BGM 을 무음 영상에 얹는다. 영상은 재인코딩하지 않는다(-c:v copy)."""
from __future__ import annotations

from pathlib import Path

from ..ffmpeg_tools import run_ffmpeg

LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"


def build_mux_args(silent_mp4: Path, narrations: list[tuple[float, Path]], bgm: Path | None, total: float,
                   out_mp4: Path, *, bgm_gain: float = 0.08, fade: float = 1.8) -> list[str]:
    """ffmpeg 인자 목록을 만든다 (실행은 하지 않는다). narrations 는 (시작 초, mp3 경로)."""
    has_bgm = bgm is not None
    if not narrations and not has_bgm:
        return ["-i", str(silent_mp4), "-c", "copy", "-movflags", "+faststart", str(out_mp4)]

    args: list[str] = ["-i", str(silent_mp4)]
    for _, p in narrations:
        args += ["-i", str(p)]
    if has_bgm:
        args += ["-stream_loop", "-1", "-i", str(bgm)]

    parts: list[str] = []
    for i, (start, _) in enumerate(narrations):
        ms = max(0, int(round(start * 1000)))
        parts.append(f"[{i + 1}:a]aresample=48000,adelay={ms}|{ms}[v{i}]")
    if len(narrations) == 1:
        voice = "[v0]"
    elif narrations:
        parts.append("".join(f"[v{i}]" for i in range(len(narrations))) +
                     f"amix=inputs={len(narrations)}:normalize=0:dropout_transition=0[voice]")
        voice = "[voice]"
    else:
        voice = ""

    if has_bgm:
        idx = len(narrations) + 1
        st = max(0.0, total - fade)
        parts.append(f"[{idx}:a]aresample=48000,atrim=0:{total:.3f},asetpts=N/SR/TB,"
                     f"volume={bgm_gain:.3f},afade=t=out:st={st:.3f}:d={fade:.2f}[bg]")

    if voice and has_bgm:
        parts.append(f"{voice}[bg]amix=inputs=2:normalize=0:dropout_transition=0[mix]")
        src = "[mix]"
    else:
        src = voice or "[bg]"
    parts.append(f"{src}{LOUDNORM},aresample=48000,aformat=channel_layouts=stereo[aout]")

    args += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[aout]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-t", f"{total:.3f}", "-movflags", "+faststart", str(out_mp4)]
    return args


def mux_audio(silent_mp4: Path, narrations: list[tuple[float, Path]], bgm: Path | None, total: float,
              out_mp4: Path, *, bgm_gain: float = 0.08, fade: float = 1.8) -> Path:
    """각 나레이션을 제 시각에 배치하고 BGM 을 깔아 섞어 영상에 붙인다. 영상은 재인코딩하지 않는다."""
    silent_mp4, out_mp4 = Path(silent_mp4), Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cues = [(s, Path(p)) for s, p in narrations if Path(p).exists()]
    track = bgm if bgm is not None and Path(bgm).exists() else None
    run_ffmpeg(build_mux_args(silent_mp4, cues, track, total, out_mp4, bgm_gain=bgm_gain, fade=fade))
    return out_mp4
