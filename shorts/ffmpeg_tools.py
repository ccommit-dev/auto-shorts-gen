from __future__ import annotations

import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


class FfmpegError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    """PATH의 ffmpeg 우선, 없으면 imageio-ffmpeg 동봉 바이너리."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [ffmpeg_exe(), "-hide_banner", "-y", "-nostdin", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise FfmpegError(f"ffmpeg 실패 (exit {proc.returncode}):\n{tail}")
    return proc


_TIME_RE = re.compile(r"time=(\d+):(\d\d):(\d\d(?:\.\d+)?)")
_RES_RE = re.compile(r"Video:.*?\s(\d{2,5})x(\d{2,5})[\s,]")


def _info_stderr(path: Path | str) -> str:
    """ffmpeg에 파일을 끝까지 디코드시켜 stderr(메타데이터 + 진행 로그)를 얻는다. ffprobe 대체."""
    cmd = [ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(path), "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 and "time=" not in proc.stderr:
        last = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "probe 실패"
        raise FfmpegError(last)
    return proc.stderr


def probe_duration(path: Path | str) -> float:
    err = _info_stderr(path)
    matches = _TIME_RE.findall(err)
    if not matches:
        raise FfmpegError(f"길이를 읽지 못했습니다: {path}")
    h, m, s = matches[-1]
    return int(h) * 3600 + int(m) * 60 + float(s)


def probe_resolution(path: Path | str) -> tuple[int, int]:
    m = _RES_RE.search(_info_stderr(path))
    if not m:
        raise FfmpegError(f"해상도를 읽지 못했습니다: {path}")
    return int(m.group(1)), int(m.group(2))


def make_silence(path: Path | str, seconds: float) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{seconds:.3f}",
                "-c:a", "libmp3lame", "-q:a", "6", str(path)])
    return path
