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


_FIT_VF = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps={FPS},format=yuv420p"


def loop_fit_clip(src: Path, duration: float, out_path: Path) -> Path:
    """클립을 앞으로만 반복/잘라 정확히 duration 초, 1080x1920으로 맞춘다."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-stream_loop", "-1", "-i", str(src), "-t", f"{duration:.3f}", "-vf", _FIT_VF,
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out_path)])
    return out_path


def speaker_segments(cues: list[Cue] | None, total: float, punch_kind: str = "talk") -> list[tuple[float, float, str]]:
    """타임라인을 (start, end, kind) 구간으로 나눈다. 동물 대사는 talk(펀치라인은 punch_kind), 나머지는 listen.
    펀치라인 이후 꼬리(tail)는 펀치라인 구간에 붙여 마지막 컷이 유지되게 한다."""
    segs: list[tuple[float, float, str]] = []
    t = 0.0
    for c in sorted(cues or [], key=lambda c: c.start):
        if c.speaker != "animal":
            continue
        if c.start > t:
            segs.append((t, c.start, "listen"))
        end = total if c.punch else c.end
        segs.append((max(t, c.start), end, punch_kind if c.punch else "talk"))
        t = end
    if t < total:
        segs.append((t, total, "listen"))
    return [(round(s, 3), round(e, 3), k) for s, e, k in segs if e - s > 0.01]


XFADE = 0.15          # 컷 크로스페이드 길이(초)
MIN_SEGMENT = 0.4     # 이보다 짧은 구간은 앞 구간에 합친다 (크로스페이드보다 길어야 함)


def merge_short_segments(segs: list[tuple[float, float, str]], min_len: float = MIN_SEGMENT) -> list[tuple[float, float, str]]:
    """너무 짧은 구간은 이웃에 흡수하고, 같은 종류가 이어지면 합친다."""
    out: list[list] = []
    for s, e, k in segs:
        if out and (e - s < min_len or out[-1][2] == k):
            out[-1][1] = e
        else:
            out.append([s, e, k])
    if len(out) > 1 and out[0][1] - out[0][0] < min_len:
        out[1][0] = out[0][0]
        out.pop(0)
    return [(round(s, 3), round(e, 3), k) for s, e, k in out]


def assemble_by_speaker(talk_clip: Path, listen_clip: Path, cues: list[Cue] | None, total: float,
                        out_path: Path, punch_clip: Path | None = None) -> Path:
    """말하는 클립/듣는 클립을 화자 구간대로 잘라 이어 붙인다 (역재생 없음).

    두 클립은 같은 장면 이미지에서 시작하므로 구간마다 0초부터 재생하면 컷의 첫 프레임이 같아 이음새가
    거의 보이지 않고, 남는 차이는 XFADE 크로스페이드로 감춘다. 크로스페이드 겹침만큼 각 구간을 길게
    잘라 자막/음성 타임라인과 어긋나지 않게 한다.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clips = {"talk": Path(talk_clip), "listen": Path(listen_clip)}
    if punch_clip is not None:
        clips["punch"] = Path(punch_clip)
    segs = merge_short_segments(speaker_segments(cues, total, "punch" if punch_clip else "talk")
                                or [(0.0, total, "listen")])
    idx = {k: i for i, k in enumerate(clips)}
    n = len(segs)
    parts, lengths = [], []
    for i, (s, e, kind) in enumerate(segs):
        length = e - s
        extra = XFADE if i < n - 1 else 0.0
        parts.append(f"[{idx[kind]}:v]trim=start=0:end={length + extra:.3f},setpts=PTS-STARTPTS,{_FIT_VF}[s{i}]")
        lengths.append(length)
    if n == 1:
        chain = "[s0]null[v]"
    else:
        steps, cur, offset = [], "s0", 0.0
        for i in range(1, n):
            offset += lengths[i - 1]
            nxt = "v" if i == n - 1 else f"x{i}"
            steps.append(f"[{cur}][s{i}]xfade=transition=fade:duration={XFADE}:offset={offset:.3f}[{nxt}]")
            cur = nxt
        chain = ";".join(steps)
    inputs = []
    for c in clips.values():
        inputs += ["-stream_loop", "-1", "-i", str(c)]
    run_ffmpeg([*inputs, "-filter_complex", ";".join(parts + [chain]), "-map", "[v]", "-t", f"{total:.3f}",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out_path)])
    return out_path


def motion_score(path: Path, w: int = 96, h: int = 160) -> float:
    """연속 프레임 평균 절대차(0~255). 정지 0.5 이하, 자연스러운 말하기 2~4, 과한 움직임 8+."""
    import subprocess
    import numpy as np
    from .ffmpeg_tools import ffmpeg_exe
    raw = subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", str(path),
                          "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    if len(frames) < 2:
        return 0.0
    return float(np.abs(np.diff(frames, axis=0)).mean())


MOTION_TARGET = {"talk": 2.5, "listen": 1.0, "punch": 3.0}


def pick_by_motion(candidates: list[Path], kind: str, target: float | None = None) -> Path:
    """움직임 점수가 목표에 가장 가까운 클립을 고른다."""
    if target is None:
        target = MOTION_TARGET.get(kind, 2.0)
    return min(candidates, key=lambda p: abs(motion_score(p) - target))


def interpolate_30fps(src: Path, out_path: Path) -> Path:
    """24fps 클립을 minterpolate 로 30fps 보간 (원본 해상도에서 수행해 빠르게)."""
    run_ffmpeg(["-i", str(src), "-vf", f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:vsbmc=1",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out_path)])
    return out_path


def closeup_crop(image, frac: float = 0.62, top: float = 0.06):
    """장면 이미지의 위쪽 중앙(얼굴 근처)을 같은 비율로 크롭한 클로즈업."""
    w, h = image.size
    cw, ch = int(w * frac), int(h * frac)
    x, y = (w - cw) // 2, int(h * top)
    return image.crop((x, y, x + cw, y + ch)).resize((w, h))


def puppet_zoom_expr(cues: list[Cue] | None, frames: int, fps: int = FPS) -> str:
    """zoompan z 식: 전체적으로 천천히 확대(1.0→1.2)하고, 동물 대사 구간에서는 말하는 듯 통통 튄다."""
    base = f"1.0+0.2*on/{max(frames, 1)}"
    talking = [c for c in (cues or []) if c.speaker == "animal"]
    if not talking:
        return base
    gate = "+".join(f"between(on/{fps},{c.start:g},{c.end:g})" for c in talking)
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
    """사용자가 assets/clips 에 넣은 mp4 사용. 파일명에 'listen' 이 있으면 듣는 클립, 나머지는 말하는 클립."""
    name = "local"

    def __init__(self, clips: list[Path] | Path):
        clips = [Path(c) for c in ([clips] if isinstance(clips, (str, Path)) else clips)]
        if not clips:
            raise RuntimeError("assets/clips 에 mp4가 없습니다")
        listen = [c for c in clips if "listen" in c.stem.lower()]
        talk = [c for c in clips if c not in listen] or listen
        self.talk, self.listen = talk[0], (listen[0] if listen else talk[0])

    def generate(self, image_path: Path, prompt: str, duration: float, out_path: Path,
                 cues: list[Cue] | None = None) -> Path:
        return assemble_by_speaker(self.talk, self.listen, cues, duration, out_path)


TALK_PROMPT = (
    "The animal stays in place and talks into the microphone: mouth moving as if speaking, small head nods, "
    "ears twitching, blinking, subtle paw gestures; steady camera, gentle natural motion"
)
LISTEN_PROMPT = (
    "The animal sits still and listens attentively to the interviewer, looking toward the microphone, "
    "mouth closed, slow blinking, slight breathing, ears perked; steady camera, minimal motion"
)
NEGATIVE_PROMPT = ("worst quality, fast motion, spinning, camera shake, blurry, jittery, distorted, "
                   "extra limbs, text, watermark")


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

    '말하는' 클립과 '듣는' 클립을 각각 만들고, 자막 타이밍대로 화자별 컷 편집한다.
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
            # RTX 50(sm_120)에서 cuDNN SDPA 는 플랜 생성이 매우 느리거나 CUDA 오류를 내므로 끈다
            torch.backends.cuda.enable_cudnn_sdp(False)
            pipe = LTXConditionPipeline.from_pretrained(ltx_model_path(self.s), dtype=torch.bfloat16)
            # 기본 디스패치가 MATH 경로로 떨어지면 VRAM 초과 → Windows 가 시스템 RAM 으로 넘겨 극도로 느려진다.
            # 메모리 효율 SDPA 를 명시하면 512x896x97 이 11.5GB, 스텝당 ~2초 (RTX 5060 Ti 16GB 기준).
            pipe.transformer.set_attention_backend(self.s.ltx_attention_backend)
            pipe.enable_model_cpu_offload()  # T5 텍스트 인코더와 트랜스포머를 번갈아 GPU 에 올림
            pipe.vae.enable_tiling()
            pipe.set_progress_bar_config(desc="LTX-Video", leave=False)
            self._pipe = pipe
        return self._pipe

    def _clip(self, image, scene_prompt: str, motion_prompt: str, seed: int, out: Path) -> Path:
        if out.exists():
            return out
        import torch
        from diffusers.utils import export_to_video
        pipe = self._pipeline()
        frames = pipe(
            prompt=f"{scene_prompt[:300]}. {motion_prompt}",  # T5 최대 128 토큰 안에 들어오도록 장면 프롬프트를 자른다
            negative_prompt=NEGATIVE_PROMPT,
            image=image,
            width=self.s.ltx_width, height=self.s.ltx_height, num_frames=self.s.ltx_num_frames,
            num_inference_steps=self.s.ltx_steps, guidance_scale=self.s.ltx_guidance,
            decode_timestep=0.03, decode_noise_scale=0.025,
            generator=torch.Generator(device="cuda").manual_seed(seed),
        ).frames[0]
        export_to_video(frames, str(out), fps=24)
        return out

    def _best_clip(self, image, prompt: str, motion_prompt: str, kind: str, base_seed: int, out_dir: Path) -> Path:
        """시드 ltx_seeds 개를 생성해 움직임이 목표에 가까운 것을 고르고, 필요하면 30fps 로 보간한다."""
        final = out_dir / f"ai_{kind}.mp4"
        if final.exists():
            return final
        cands = [self._clip(image, prompt, motion_prompt, base_seed + 10 * k, out_dir / f"ai_{kind}_s{k}.mp4")
                 for k in range(max(1, self.s.ltx_seeds))]
        best = pick_by_motion(cands, kind) if len(cands) > 1 else cands[0]
        if self.s.ltx_interpolate:
            return interpolate_30fps(best, final)
        import shutil
        shutil.copyfile(best, final)
        return final

    def generate(self, image_path: Path, prompt: str, duration: float, out_path: Path,
                 cues: list[Cue] | None = None) -> Path:
        from PIL import Image
        out_path = Path(out_path)
        out_dir = out_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        image = Image.open(image_path).convert("RGB").resize((self.s.ltx_width, self.s.ltx_height), Image.LANCZOS)
        seed = self.s.ltx_seed
        talk = self._best_clip(image, prompt, TALK_PROMPT, "talk", seed, out_dir)
        listen = self._best_clip(image, prompt, LISTEN_PROMPT, "listen", seed + 1, out_dir)
        punch = None
        if self.s.ltx_closeup and any(c.punch for c in (cues or [])):
            punch = self._best_clip(closeup_crop(image), prompt, TALK_PROMPT, "punch", seed + 2, out_dir)
        return assemble_by_speaker(talk, listen, cues, duration, out_path, punch_clip=punch)


class KlingVideoProvider:
    """Kling 3.0 image-to-video API (유료, ALLOW_PAID 필요). 클립 하나를 앞으로 반복한다."""
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
        body = {"contents": [{"type": "prompt", "text": f"{prompt}. {TALK_PROMPT}"[:2500]},
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
