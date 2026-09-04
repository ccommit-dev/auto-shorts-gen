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
    tts_voice_animal: str = "ko-KR-SunHiNeural"
    tts_voice_reporter: str = "ko-KR-InJoonNeural"
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
