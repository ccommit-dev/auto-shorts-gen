from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .image_gen import (GeminiImageProvider, ImageProvider, LocalImageProvider, PlaceholderImageProvider,
                        PollinationsImageProvider)
from .script_gen import ClaudeScriptProvider, GeminiScriptProvider, PlaceholderScriptProvider, ScriptProvider
from .tts import EdgeTTSProvider, ElevenLabsTTSProvider, SilentTTSProvider, TTSProvider
from .usage_ledger import UsageLedger
from .video_gen import (KenBurnsVideoProvider, KlingVideoProvider, LocalAIVideoProvider, LocalClipProvider,
                        VideoProvider, ltx_available)


@dataclass
class Providers:
    script: ScriptProvider
    image: ImageProvider
    tts: TTSProvider
    video: VideoProvider


def _first_file(folder: Path, exts: tuple[str, ...]) -> Path | None:
    if not folder.exists():
        return None
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in exts)
    return files[0] if files else None


def build_providers(settings: Settings, *, dry_run: bool, video_provider: str | None, image_provider: str | None,
                    script_provider: str | None, ledger: UsageLedger, tts_provider: str | None = None) -> Providers:
    """설정/옵션에 따라 단계별 공급자를 고른다. 기본은 전부 무료."""
    assets = Path(settings.assets_dir)
    if dry_run:
        return Providers(PlaceholderScriptProvider(), PlaceholderImageProvider(settings.font_path),
                         SilentTTSProvider(), KenBurnsVideoProvider())

    sp = script_provider or "gemini"
    if sp == "claude":
        script = ClaudeScriptProvider(settings)
    elif sp == "placeholder":
        script = PlaceholderScriptProvider()
    else:
        script = GeminiScriptProvider(settings, ledger)

    local_img = _first_file(assets / "images", (".png", ".jpg", ".jpeg"))
    ip = image_provider or ("local" if local_img else "pollinations")
    if ip == "local":
        if not local_img:
            raise RuntimeError("assets/images 에 이미지가 없습니다")
        image = LocalImageProvider(local_img)
    elif ip == "gemini":
        image = GeminiImageProvider(settings)
    elif ip == "placeholder":
        image = PlaceholderImageProvider(settings.font_path)
    else:
        image = PollinationsImageProvider(settings, ledger)

    tp = tts_provider or "edge"
    tts = ElevenLabsTTSProvider(settings) if tp == "elevenlabs" else EdgeTTSProvider(settings)

    local_clip = _first_file(assets / "clips", (".mp4", ".mov"))
    vp = video_provider or settings.video_provider
    if vp == "auto":
        vp = "local" if local_clip else ("ltx" if ltx_available() else "kenburns")
    if vp == "local":
        if not local_clip:
            raise RuntimeError("assets/clips 에 mp4가 없습니다")
        video = LocalClipProvider(local_clip)
    elif vp == "kling":
        video = KlingVideoProvider(settings)
    elif vp == "ltx":
        video = LocalAIVideoProvider(settings)
    else:
        video = KenBurnsVideoProvider()
    return Providers(script, image, tts, video)
