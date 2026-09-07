from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ffmpeg_tools import run_ffmpeg
from .timing import Cue
from .tts import Utterance

TITLE_Y = 130          # 상단 제목 y
SUBTITLE_BOTTOM = 260  # 하단 자막 아래 여백
BGM_VOLUME = 0.12
SFX_VOLUME = 0.5
PUNCH_ZOOM = 1.08      # 펀치라인 순간 줌인 배율
END_FREEZE = 0.5       # 마지막 정지 프레임(초)
_AFMT = "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"
# 대사에 아주 가벼운 공간감 (TTS 의 건조함 완화)
DIALOGUE_REVERB = "aecho=in_gain=0.9:out_gain=0.9:delays=38:decays=0.16"
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"


@dataclass
class Overlay:
    png: Path
    start: float
    end: float


@dataclass
class Sfx:
    path: Path
    at: float


def build_compose_command(*, video: Path, title_png: Path, overlays: list[Overlay], cues: list[Cue],
                          utterances: list[Utterance], bgm: Path | None, total: float, out_path: Path,
                          punch: tuple[float, float] | None = None, sfx: list[Sfx] | None = None,
                          title_frames: list[Overlay] | None = None, end_freeze: float = END_FREEZE) -> list[str]:
    """모션 영상 + 제목/자막 PNG + 대사 음성(리버브) + BGM + 효과음 + 펀치라인 줌 + 마지막 정지 + loudnorm 을
    한 번의 ffmpeg 호출로 합성한다."""
    sfx = sfx or []
    title_frames = title_frames or []
    inputs: list[str] = ["-i", str(video), "-i", str(title_png)]
    for o in title_frames:
        inputs += ["-i", str(o.png)]
    for o in overlays:
        inputs += ["-i", str(o.png)]
    audio_base = 2 + len(title_frames) + len(overlays)
    for u in utterances:
        inputs += ["-i", str(u.path)]
    sfx_base = audio_base + len(utterances)
    for s in sfx:
        inputs += ["-i", str(s.path)]
    bgm_idx = None
    if bgm is not None:
        bgm_idx = sfx_base + len(sfx)
        inputs += ["-stream_loop", "-1", "-i", str(bgm)]

    # 영상: 마지막 end_freeze 초는 정지 프레임
    body = max(0.1, total - end_freeze) if end_freeze > 0 else total
    f = [f"[0:v]trim=0:{body:.3f},setpts=PTS-STARTPTS,scale=1080:1920,format=yuv420p"
         + (f",tpad=stop_mode=clone:stop_duration={end_freeze:.3f}" if end_freeze > 0 else "") + "[vbase]"]
    if punch is not None:
        zw, zh = round(1080 * PUNCH_ZOOM / 2) * 2, round(1920 * PUNCH_ZOOM / 2) * 2
        f.append(f"[vbase]split[vb0][vb1];[vb1]scale={zw}:{zh},crop=1080:1920[vz];"
                 f"[vb0][vz]overlay=0:0:enable='between(t,{punch[0]:g},{punch[1]:g})'[v0]")
    else:
        f.append("[vbase]null[v0]")
    # 제목: 팝인 프레임들 → 최종 제목
    cur = "v0"
    for i, o in enumerate(title_frames):
        nxt = f"vt{i}"
        f.append(f"[{cur}][{2 + i}:v]overlay=(W-w)/2:{TITLE_Y}+({320}-h)/2:enable='between(t,{o.start:g},{o.end:g})'[{nxt}]")
        cur = nxt
    title_start = title_frames[-1].end if title_frames else 0.0
    f.append(f"[{cur}][1:v]overlay=(W-w)/2:{TITLE_Y}:enable='gte(t,{title_start:g})'[v1]")
    cur = "v1"
    ob = 2 + len(title_frames)
    for i, o in enumerate(overlays):
        nxt = f"v{i + 2}"
        f.append(f"[{cur}][{ob + i}:v]overlay=(W-w)/2:H-h-{SUBTITLE_BOTTOM}"
                 f":enable='between(t,{o.start:g},{o.end:g})'[{nxt}]")
        cur = nxt
    f.append(f"[{cur}]null[vout]")

    labels = []
    for k, (u, cue) in enumerate(zip(utterances, cues)):
        ms = int(round(cue.start * 1000))
        f.append(f"[{audio_base + k}:a]{_AFMT},{DIALOGUE_REVERB},adelay={ms}|{ms}[a{k}]")
        labels.append(f"[a{k}]")
    for j, s in enumerate(sfx):
        ms = int(round(s.at * 1000))
        f.append(f"[{sfx_base + j}:a]{_AFMT},volume={SFX_VOLUME},adelay={ms}|{ms}[sfx{j}]")
        labels.append(f"[sfx{j}]")
    if bgm_idx is not None:
        f.append(f"[{bgm_idx}:a]{_AFMT},volume={BGM_VOLUME},afade=t=out:st={max(0.0, total - 1.0):.3f}:d=1,"
                 f"atrim=0:{total:.3f}[abgm]")
        labels.append("[abgm]")
    n = len(labels)
    mix = f"{labels[0]}" if n == 1 else f"{''.join(labels)}amix=inputs={n}:normalize=0:dropout_transition=0,"
    f.append(f"{mix}apad,atrim=0:{total:.3f},{LOUDNORM}[aout]")

    return [*inputs, "-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out_path)]


def compose(**kwargs) -> Path:
    out = Path(kwargs["out_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(build_compose_command(**kwargs))
    return out
