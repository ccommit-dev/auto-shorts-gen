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
from .timing import Cue

FPS = 30


class VideoProvider(Protocol):
    def generate(self, image_path: Path, prompt: str, duration: float, out_path: Path,
                 cues: list[Cue] | None = None) -> Path: ...


def loop_fit_clip(src: Path, duration: float, out_path: Path) -> Path:
    """클립을 반복/잘라 정확히 duration 초, 1080x1920으로 맞춘다."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-stream_loop", "-1", "-i", str(src), "-t", f"{duration:.3f}",
                "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps={FPS},format=yuv420p",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out_path)])
    return out_path


def pingpong_clip(src: Path, out_path: Path) -> Path:
    """클립 + 역재생을 이어 붙여 끊김 없이 반복 가능한 왕복 클립을 만든다."""
    out_path = Path(out_path)
    run_ffmpeg(["-i", str(src), "-filter_complex",
                "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,format=yuv420p[v]",
                "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out_path)])
    return out_path


def puppet_zoom_expr(cues: list[Cue] | None, frames: int, fps: int = FPS) -> str:
    """zoompan z 식: 전체적으로 천천히 확대(1.0→1.2)하고, 동물 대사 구간에서는 말하는 듯 통통 튄다."""
    base = f"1.0+0.2*on/{max(frames, 1)}"
    talking = [c for c in (cues or []) if c.speaker == "animal"]
    if not talking:
        return base
    gate = "+".join(f"between(on/{fps},{c.start:g},{c.end:g})" for c in talking)
    # 6.5Hz 정도의 작은 진동 + 약간의 상하 흔들림 → 자막과 동기화된 '말하는' 느낌
    return f"{base}+0.03*gt({gate},0)*abs(sin(on*1.35))"


class KenBurnsVideoProvider:
    """정지 이미지에 ffmpeg zoompan 모션. cues 가 있으면 동물 대사 구간에서 퍼펫처럼 움직인다 (무료)."""
    name = "kenburns"

    def generate(self, image_path: Path, prompt: str, duration: float, out_path: Path,
                 cues: list[Cue] | None = None) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        frames = max(1, math.ceil(duration * FPS))
        z = puppet_zoom_expr(cues, frames)
        y = "ih/2-(ih/zoom/2)"
        if any(c.speaker == "animal" for c in (cues or [])):
            gate = "+".join(f"between(on/{FPS},{c.start:g},{c.end:g})" for c in cues if c.speaker == "animal")
            y = f"ih/2-(ih/zoom/2)+gt({gate},0)*12*sin(on*1.35)"
        vf = (f"scale=2160:3840,zoompan=z='{z}':d={frames}"
              f":x='iw/2-(iw/zoom/2)':y='{y}':s=1080x1920:fps={FPS},format=yuv420p")
        run_ffmpeg(["-i", str(image_path), "-vf", vf, "-t", f"{duration:.3f}",
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out_path)])
        return out_path


class LocalClipProvider:
    """사용자가 assets/clips 에 넣은 mp4 사용 (예: Kling 웹앱 무료 크레딧으로 만든 클립)."""
    name = "local"

    def __init__(self, clip: Path):
        self.clip = Path(clip)

    def generate(self, image_path: Path, prompt: str, duration: float, out_path: Path,
                 cues: list[Cue] | None = None) -> Path:
        pp = Path(out_path).with_name("clip_pingpong.mp4")
        return loop_fit_clip(pingpong_clip(self.clip, pp), duration, out_path)


MOTION_PROMPT = (
    "The animal talks animatedly into the microphone, mouth moving as if speaking, head tilting, "
    "ears twitching, paws gesturing, natural blinking; the interviewer's hand holds the microphone steady; "
    "warm street lights flicker softly; camera slowly pushes in; smooth realistic motion, high quality"
)
NEGATIVE_PROMPT = "worst quality, inconsistent motion, blurry, jittery, distorted, extra limbs, text, watermark"


def ltx_model_path(settings: Settings) -> str:
    """models/<repo 이름> 폴더가 있으면 그 경로, 없으면 HF 저장소 id."""
    local = Path(settings.models_dir) / settings.ltx_model.split("/")[-1]
    return str(local) if (local / "model_index.json").exists() else settings.ltx_model


def ltx_available() -> bool:
    try:
        import torch
        import diffusers  # noqa: F401
        return bool(torch.cuda.is_available())
    except Exception:
        return False


class LocalAIVideoProvider:
    """로컬 GPU에서 오픈소스 LTX-Video(2B)로 image-to-video 생성 (무료, NVIDIA GPU 필요).

    5초 남짓의 클립을 만들고 왕복(ping-pong) 반복으로 전체 길이를 채운다.
    """
    name = "ltx"

    def __init__(self, settings: Settings):
        ensure_allowed(self.name, settings.allow_paid)
        if not ltx_available():
            raise RuntimeError("로컬 AI 영상은 CUDA GPU + torch/diffusers 가 필요합니다 (pip install -r requirements-gpu.txt).")
        self.s = settings
        self._pipe = None

    def _pipeline(self):
        if self._pipe is None:
            import torch
            from diffusers import LTXConditionPipeline
            pipe = LTXConditionPipeline.from_pretrained(ltx_model_path(self.s), torch_dtype=torch.bfloat16)
            pipe.enable_model_cpu_offload()  # 16GB급 GPU에서 T5 텍스트 인코더와 트랜스포머를 번갈아 올림
            pipe.vae.enable_tiling()
            self._pipe = pipe
        return self._pipe

    def generate(self, image_path: Path, prompt: str, duration: float, out_path: Path,
                 cues: list[Cue] | None = None) -> Path:
        import torch
        from diffusers.utils import export_to_video
        from PIL import Image
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pipe = self._pipeline()
        width, height = self.s.ltx_width, self.s.ltx_height  # 32의 배수, 9:16
        image = Image.open(image_path).convert("RGB").resize((width, height), Image.LANCZOS)
        num_frames = self.s.ltx_num_frames  # 8k+1
        generator = torch.Generator(device="cuda").manual_seed(self.s.ltx_seed)
        frames = pipe(
            prompt=f"{prompt}. {MOTION_PROMPT}",
            negative_prompt=NEGATIVE_PROMPT,
            image=image,
            width=width, height=height, num_frames=num_frames,
            num_inference_steps=self.s.ltx_steps, guidance_scale=self.s.ltx_guidance,
            decode_timestep=0.03, decode_noise_scale=0.025,
            generator=generator,
        ).frames[0]
        raw = out_path.with_name("ai_raw.mp4")
        export_to_video(frames, str(raw), fps=24)
        pp = out_path.with_name("ai_pingpong.mp4")
        return loop_fit_clip(pingpong_clip(raw, pp), duration, out_path)


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

    def generate(self, image_path: Path, prompt: str, duration: float, out_path: Path,
                 cues: list[Cue] | None = None) -> Path:
        secs = int(min(15, max(3, math.ceil(duration))))
        ext_id = uuid.uuid4().hex
        body = {"contents": [{"type": "prompt", "text": f"{prompt}. {MOTION_PROMPT}"[:2500]},
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
