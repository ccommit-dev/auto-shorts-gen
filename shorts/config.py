from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


def _bool(v: str | None, default: bool) -> bool:
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(v: str | None, default: int) -> int:
    return int(v) if v and v.strip() else default


def _csv(v: str | None) -> tuple[str, ...]:
    return tuple(x.strip() for x in (v or "").split(",") if x.strip())


@dataclass
class Settings:
    # 무료 기본 공급자
    gemini_api_key: str | None = None
    gemini_text_model: str = "gemini-3.5-flash"
    gemini_daily_text_cap: int = 50
    pollinations_daily_cap: int = 100
    image_seed: int = 0  # 0이면 매번 랜덤, 그 외는 고정 (같은 캐릭터 재현)
    image_style_suffix: str = ("mouth closed, looking at the camera, centered, full body visible, "
                               "photorealistic, sharp focus, vertical 9:16")
    tts_voice_animal: str = "ko-KR-SunHiNeural"
    tts_voice_reporter: str = "ko-KR-HyunsuMultilingualNeural"
    # 유료 게이트
    allow_paid: bool = False
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5"
    gemini_image_model: str = "gemini-3.1-flash-image"
    kling_api_key: str | None = None
    kling_base_url: str = "https://api-singapore.klingai.com"
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_animal: str = "EXAVITQu4vr4xnSDxMaL"
    elevenlabs_voice_reporter: str = "JBFqnCBsd6RMkjVDRZzb"
    # 로컬 AI 영상 (무료, NVIDIA GPU)
    video_provider: str = "auto"  # auto | kenburns | local | ltx | kling
    ltx_model: str = "Lightricks/LTX-Video-0.9.5"
    models_dir: str = "models"  # 다운로드한 모델 폴더 (HF 캐시의 심볼릭 링크 문제 회피)
    ltx_width: int = 512
    ltx_height: int = 896
    ltx_num_frames: int = 161
    ltx_steps: int = 40
    ltx_guidance: float = 4.0
    ltx_seed: int = 42
    ltx_attention_backend: str = "_native_efficient"  # diffusers attention backend 이름
    ltx_seeds: int = 2            # 시드 몇 개를 만들어 움직임이 적당한 클립을 고를지
    ltx_interpolate: bool = True  # 24fps → 30fps minterpolate 보간
    ltx_closeup: bool = True      # 펀치라인용 클로즈업 클립 추가 생성
    # 모션 그래픽 제품 소개 영상 (promo 모드)
    promo_width: int = 1920
    promo_height: int = 1080
    promo_fps: int = 30
    promo_accent: str = "#1F7A45"
    promo_voice: str = "ko-KR-HyunsuMultilingualNeural"
    promo_browser: str = "msedge"       # msedge | chrome | chromium
    promo_capture_quality: int = 95     # 프레임 JPEG 품질
    promo_crf: int = 19                 # h264 품질 (낮을수록 고화질)
    promo_bgm_gain: float = 0.08
    promo_min_scene: float = 2.8        # 장면 최소 길이(초)
    promo_lead: float = 0.5             # 장면 시작~나레이션 시작
    # 렌더링/출력
    font_path: str = "C:/Windows/Fonts/malgunbd.ttf"
    output_dir: str = "output"
    assets_dir: str = "assets"
    use_os_truststore: bool = True
    # 배포
    auto_publish: tuple[str, ...] = ()
    youtube_privacy: str = "private"
    youtube_client_secrets: str = "client_secrets.json"
    youtube_token: str = "token.json"
    ig_user_id: str | None = None
    ig_access_token: str | None = None
    ig_media_host: str = "none"  # none | catbox | copydir
    ig_copydir_path: str | None = None
    ig_copydir_base_url: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        g = env.get
        return cls(
            gemini_api_key=g("GEMINI_API_KEY") or None,
            gemini_text_model=g("GEMINI_TEXT_MODEL") or cls.gemini_text_model,
            gemini_daily_text_cap=_int(g("GEMINI_DAILY_TEXT_CAP"), cls.gemini_daily_text_cap),
            pollinations_daily_cap=_int(g("POLLINATIONS_DAILY_CAP"), cls.pollinations_daily_cap),
            image_seed=_int(g("IMAGE_SEED"), cls.image_seed),
            image_style_suffix=g("IMAGE_STYLE_SUFFIX") or cls.image_style_suffix,
            tts_voice_animal=g("TTS_VOICE_ANIMAL") or cls.tts_voice_animal,
            tts_voice_reporter=g("TTS_VOICE_REPORTER") or cls.tts_voice_reporter,
            allow_paid=_bool(g("ALLOW_PAID"), False),
            anthropic_api_key=g("ANTHROPIC_API_KEY") or None,
            claude_model=g("CLAUDE_MODEL") or cls.claude_model,
            gemini_image_model=g("GEMINI_IMAGE_MODEL") or cls.gemini_image_model,
            kling_api_key=g("KLING_API_KEY") or None,
            kling_base_url=g("KLING_BASE_URL") or cls.kling_base_url,
            elevenlabs_api_key=g("ELEVENLABS_API_KEY") or None,
            elevenlabs_voice_animal=g("ELEVENLABS_VOICE_ANIMAL") or cls.elevenlabs_voice_animal,
            elevenlabs_voice_reporter=g("ELEVENLABS_VOICE_REPORTER") or cls.elevenlabs_voice_reporter,
            video_provider=(g("VIDEO_PROVIDER") or cls.video_provider).lower(),
            ltx_model=g("LTX_MODEL") or cls.ltx_model,
            models_dir=g("MODELS_DIR") or cls.models_dir,
            ltx_width=_int(g("LTX_WIDTH"), cls.ltx_width),
            ltx_height=_int(g("LTX_HEIGHT"), cls.ltx_height),
            ltx_num_frames=_int(g("LTX_NUM_FRAMES"), cls.ltx_num_frames),
            ltx_steps=_int(g("LTX_STEPS"), cls.ltx_steps),
            ltx_guidance=float(g("LTX_GUIDANCE") or cls.ltx_guidance),
            ltx_seed=_int(g("LTX_SEED"), cls.ltx_seed),
            ltx_attention_backend=g("LTX_ATTENTION_BACKEND") or cls.ltx_attention_backend,
            ltx_seeds=_int(g("LTX_SEEDS"), cls.ltx_seeds),
            ltx_interpolate=_bool(g("LTX_INTERPOLATE"), cls.ltx_interpolate),
            ltx_closeup=_bool(g("LTX_CLOSEUP"), cls.ltx_closeup),
            promo_width=_int(g("PROMO_WIDTH"), cls.promo_width),
            promo_height=_int(g("PROMO_HEIGHT"), cls.promo_height),
            promo_fps=_int(g("PROMO_FPS"), cls.promo_fps),
            promo_accent=g("PROMO_ACCENT") or cls.promo_accent,
            promo_voice=g("PROMO_VOICE") or cls.promo_voice,
            promo_browser=(g("PROMO_BROWSER") or cls.promo_browser).lower(),
            promo_capture_quality=_int(g("PROMO_CAPTURE_QUALITY"), cls.promo_capture_quality),
            promo_crf=_int(g("PROMO_CRF"), cls.promo_crf),
            promo_bgm_gain=float(g("PROMO_BGM_GAIN") or cls.promo_bgm_gain),
            promo_min_scene=float(g("PROMO_MIN_SCENE") or cls.promo_min_scene),
            promo_lead=float(g("PROMO_LEAD") or cls.promo_lead),
            font_path=g("FONT_PATH") or cls.font_path,
            output_dir=g("OUTPUT_DIR") or cls.output_dir,
            assets_dir=g("ASSETS_DIR") or cls.assets_dir,
            use_os_truststore=_bool(g("USE_OS_TRUSTSTORE"), True),
            auto_publish=_csv(g("AUTO_PUBLISH")),
            youtube_privacy=g("YOUTUBE_PRIVACY") or cls.youtube_privacy,
            youtube_client_secrets=g("YOUTUBE_CLIENT_SECRETS") or cls.youtube_client_secrets,
            youtube_token=g("YOUTUBE_TOKEN") or cls.youtube_token,
            ig_user_id=g("IG_USER_ID") or None,
            ig_access_token=g("IG_ACCESS_TOKEN") or None,
            ig_media_host=(g("IG_MEDIA_HOST") or cls.ig_media_host).lower(),
            ig_copydir_path=g("IG_COPYDIR_PATH") or None,
            ig_copydir_base_url=g("IG_COPYDIR_BASE_URL") or None,
        )


def load_settings(dotenv_path: str | None = ".env") -> Settings:
    import os
    if dotenv_path:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path, override=False)
    return Settings.from_env(os.environ)
