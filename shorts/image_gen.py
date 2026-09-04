from __future__ import annotations

import io
import random
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFont

from .config import Settings
from .cost_guard import ensure_allowed
from .usage_ledger import UsageLedger

PORTRAIT = (1080, 1920)


class ImageProvider(Protocol):
    def generate(self, prompt: str, out_path: Path) -> Path: ...


def fit_portrait(img: Image.Image, size: tuple[int, int] = PORTRAIT) -> Image.Image:
    """비율 유지 확대 후 중앙 크롭(cover)."""
    img = img.convert("RGB")
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (resized.width - tw) // 2, (resized.height - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def _save(img: Image.Image, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fit_portrait(img).save(out_path, "PNG")
    return out_path


class PollinationsImageProvider:
    """pollinations.ai 무료 텍스트→이미지 (키 불필요)."""
    name = "pollinations"
    BASE = "https://image.pollinations.ai/prompt/"

    def __init__(self, settings: Settings, ledger: UsageLedger, session=None):
        self.s, self.ledger = settings, ledger
        if session is None:
            import requests
            session = requests.Session()
        self.session = session

    def generate(self, prompt: str, out_path: Path) -> Path:
        ensure_allowed(self.name, self.s.allow_paid)
        self.ledger.reserve(self.name, self.s.pollinations_daily_cap)
        url = self.BASE + quote(prompt[:800], safe="")
        params = {"width": 1080, "height": 1920, "nologo": "true", "seed": random.randint(1, 10 ** 9)}
        last = None
        for attempt in range(3):
            resp = self.session.get(url, params=params, timeout=180)
            ctype = str(resp.headers.get("content-type", ""))
            if resp.status_code == 200 and ctype.startswith("image/"):
                return _save(Image.open(io.BytesIO(resp.content)), out_path)
            last = f"HTTP {resp.status_code} {ctype}"
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            break
        raise RuntimeError(f"pollinations 이미지 생성 실패: {last}")


class GeminiImageProvider:
    """Gemini 이미지 생성 (유료, ALLOW_PAID 필요)."""
    name = "gemini-image"

    def __init__(self, settings: Settings):
        ensure_allowed(self.name, settings.allow_paid)
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY가 없습니다.")
        self.s = settings

    def generate(self, prompt: str, out_path: Path) -> Path:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=self.s.gemini_api_key)
        resp = client.models.generate_content(
            model=self.s.gemini_image_model, contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"],
                                               image_config=types.ImageConfig(aspect_ratio="9:16")))
        for cand in resp.candidates or []:
            for part in (cand.content.parts if cand.content else None) or []:
                data = getattr(getattr(part, "inline_data", None), "data", None)
                if data:
                    return _save(Image.open(io.BytesIO(data)), out_path)
        raise RuntimeError("Gemini가 이미지를 반환하지 않았습니다")


class LocalImageProvider:
    name = "local"

    def __init__(self, src: Path):
        self.src = Path(src)

    def generate(self, prompt: str, out_path: Path) -> Path:
        return _save(Image.open(self.src), out_path)


class PlaceholderImageProvider:
    name = "placeholder"

    def __init__(self, font_path: str | None = None):
        self.font_path = font_path

    def generate(self, prompt: str, out_path: Path) -> Path:
        w, h = PORTRAIT
        # 세로 그라데이션을 한 줄 만들어 세로로 늘려 빠르게 생성
        strip = Image.new("RGB", (1, h))
        px = strip.load()
        for y in range(h):
            px[0, y] = (30 + y * 120 // h, 40, 60 + y * 150 // h)
        img = strip.resize((w, h))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(self.font_path, 40) if self.font_path else ImageFont.load_default(40)
        except OSError:
            font = ImageFont.load_default(40)
        d.multiline_text((60, h // 2 - 100), "[dry-run scene]\n" + prompt[:120], fill="white", font=font)
        return _save(img, out_path)
