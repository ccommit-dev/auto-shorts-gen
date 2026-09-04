from __future__ import annotations

import base64
import math
import time
import uuid
from pathlib import Path
from typing import Protocol

from .config import Settings
from .cost_guard import ensure_allowed
from .ffmpeg_tools import run_ffmpeg

FPS = 30


class VideoProvider(Protocol):
    def generate(self, image_path: Path, prompt: str, duration: float, out_path: Path) -> Path: ...


def loop_fit_clip(src: Path, duration: float, out_path: Path) -> Path:
    """클립을 반복/잘라 정확히 duration 초, 1080x1920으로 맞춘다."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-stream_loop", "-1", "-i", str(src), "-t", f"{duration:.3f}",
                "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps={FPS},format=yuv420p",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out_path)])
    return out_path


class KenBurnsVideoProvider:
    """정지 이미지에 ffmpeg zoompan으로 서서히 확대되는 모션 (무료)."""
    name = "kenburns"

    def generate(self, image_path: Path, prompt: str, duration: float, out_path: Path) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        frames = max(1, math.ceil(duration * FPS))
        step = 0.25 / frames  # 1.0 -> 1.25배
        vf = (f"scale=2160:3840,zoompan=z='min(zoom+{step:.6f},1.25)':d={frames}"
              f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={FPS},format=yuv420p")
        run_ffmpeg(["-i", str(image_path), "-vf", vf, "-t", f"{duration:.3f}",
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out_path)])
        return out_path


class LocalClipProvider:
    """사용자가 assets/clips 에 넣은 mp4 사용 (예: Kling 웹앱 무료 크레딧으로 만든 클립)."""
    name = "local"

    def __init__(self, clip: Path):
        self.clip = Path(clip)

    def generate(self, image_path: Path, prompt: str, duration: float, out_path: Path) -> Path:
        return loop_fit_clip(self.clip, duration, out_path)


class KlingVideoProvider:
    """Kling 3.0 image-to-video API (유료, ALLOW_PAID 필요)."""
    name = "kling"

    def __init__(self, settings: Settings, session=None, sleep=time.sleep):
        ensure_allowed(self.name, settings.allow_paid)
        if not settings.kling_api_key:
            raise RuntimeError("KLING_API_KEY가 없습니다.")
        self.s, self.sleep = settings, sleep
        if session is None:
            import requests
            session = requests.Session()
        self.session = session

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.s.kling_api_key}", "Content-Type": "application/json"}

    def generate(self, image_path: Path, prompt: str, duration: float, out_path: Path) -> Path:
        secs = int(min(15, max(3, math.ceil(duration))))
        ext_id = uuid.uuid4().hex
        body = {"contents": [{"type": "prompt", "text": prompt[:2500]},
                             {"type": "first_frame", "url": base64.b64encode(Path(image_path).read_bytes()).decode()}],
                "settings": {"resolution": "1080p", "duration": secs, "audio": "off", "multi_shot": False},
                "options": {"external_task_id": ext_id, "watermark_info": {"enabled": False}}}
        r = self.session.post(f"{self.s.kling_base_url}/image-to-video/kling-3.0",
                              headers=self._headers(), json=body, timeout=60)
        data = r.json() if r.content else {}
        if r.status_code != 200 or data.get("code") != 0:
            raise RuntimeError(f"Kling 생성 요청 실패: HTTP {r.status_code} {data}")
        video_url = None
        for _ in range(90):  # 최대 15분
            self.sleep(10)
            q = self.session.get(f"{self.s.kling_base_url}/tasks", params={"external_task_ids": ext_id},
                                 headers=self._headers(), timeout=60)
            tasks = (q.json() if q.content else {}).get("data") or []
            if not tasks:
                continue
            t = tasks[0]
            if t.get("status") == "succeeded":
                vids = [o for o in t.get("outputs", []) if o.get("type") == "video"]
                video_url = vids[0]["url"] if vids else None
                break
            if t.get("status") == "failed":
                raise RuntimeError(f"Kling 작업 실패: {t.get('message')}")
        if not video_url:
            raise RuntimeError("Kling 작업이 시간 내에 끝나지 않았습니다")
        raw = Path(out_path).with_name("kling_raw.mp4")
        raw.write_bytes(self.session.get(video_url, timeout=300).content)
        return loop_fit_clip(raw, duration, out_path)
