from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from .config import Settings
from .cost_guard import ensure_allowed
from .ffmpeg_tools import make_silence, probe_duration
from .script_model import Script
from .timing import even_words


@dataclass
class Utterance:
    index: int
    speaker: str
    text: str
    path: Path
    duration: float
    words: list[tuple[float, float, str]] = field(default_factory=list)  # mp3 기준 상대 시각


def words_path(mp3: Path) -> Path:
    return Path(mp3).with_suffix(".words.jsonl")


def load_words(mp3: Path, text: str, duration: float) -> list[tuple[float, float, str]]:
    """edge-tts WordBoundary 메타(100ns 단위)를 읽고, 없거나 비어 있으면 균등 분배."""
    p = words_path(mp3)
    out: list[tuple[float, float, str]] = []
    if p.exists():
        for line in p.read_text("utf-8").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "WordBoundary":
                continue
            start = d["offset"] / 1e7
            end = min(duration, (d["offset"] + d.get("duration", 0)) / 1e7)
            out.append((round(start, 3), round(max(end, start + 0.05), 3), str(d.get("text", "")).strip()))
    return out or even_words(text, duration)


class TTSProvider(Protocol):
    def synthesize(self, text: str, speaker: str, out_path: Path, index: int = 0) -> Path: ...


ANIMAL_VARIATIONS = [("+8%", "+20Hz"), ("+4%", "+16Hz"), ("+12%", "+24Hz"), ("+6%", "+22Hz")]
REPORTER_VARIATIONS = [("+0%", "+0Hz"), ("+3%", "+2Hz"), ("-2%", "-2Hz")]
NARRATOR_VARIATIONS = [("+0%", "+0Hz")]  # 제품 소개 나레이션은 톤을 흔들지 않는다


def voice_variation(speaker: str, index: int) -> tuple[str, str]:
    """줄마다 rate/pitch 를 조금씩 바꿔 같은 톤이 반복되는 TTS 티를 줄인다."""
    table = {"animal": ANIMAL_VARIATIONS, "narrator": NARRATOR_VARIATIONS}.get(speaker, REPORTER_VARIATIONS)
    return table[index % len(table)]


class EdgeTTSProvider:
    """Microsoft Edge 신경망 음성 (무료). 단어 타이밍을 <mp3>.words.jsonl 에 함께 저장한다."""
    name = "edge-tts"

    def __init__(self, settings: Settings):
        ensure_allowed(self.name, settings.allow_paid)
        self.voices = {"animal": settings.tts_voice_animal, "reporter": settings.tts_voice_reporter,
                       "narrator": settings.promo_voice}

    def synthesize(self, text: str, speaker: str, out_path: Path, index: int = 0) -> Path:
        import edge_tts
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rate, pitch = voice_variation(speaker, index)
        voice = self.voices.get(speaker, self.voices["animal"])
        comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
        comm.save_sync(str(out_path), str(words_path(out_path)))
        return out_path


class ElevenLabsTTSProvider:
    """ElevenLabs (유료, ALLOW_PAID 필요)."""
    name = "elevenlabs"

    def __init__(self, settings: Settings, session=None):
        ensure_allowed(self.name, settings.allow_paid)
        if not settings.elevenlabs_api_key:
            raise RuntimeError("ELEVENLABS_API_KEY가 없습니다.")
        self.s = settings
        if session is None:
            import requests
            session = requests.Session()
        self.session = session
        self.voices = {"animal": settings.elevenlabs_voice_animal, "reporter": settings.elevenlabs_voice_reporter}

    def synthesize(self, text: str, speaker: str, out_path: Path, index: int = 0) -> Path:
        vid = self.voices.get(speaker, self.voices["animal"])
        r = self.session.post(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
                              headers={"xi-api-key": self.s.elevenlabs_api_key, "accept": "audio/mpeg"},
                              json={"text": text, "model_id": "eleven_multilingual_v2"}, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"ElevenLabs 실패: HTTP {r.status_code} {r.text[:200]}")
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(r.content)
        return out_path


class SilentTTSProvider:
    """dry-run용: 글자 수에 비례한 무음."""
    name = "placeholder"

    def synthesize(self, text: str, speaker: str, out_path: Path, index: int = 0) -> Path:
        return make_silence(out_path, 0.5 + 0.12 * len(text))


def synthesize_lines(script: Script, provider: TTSProvider, path_for: Callable[[int], Path]) -> list[Utterance]:
    out = []
    for i, line in enumerate(script.lines):
        p = Path(path_for(i))
        if not p.exists():
            provider.synthesize(line.text, line.speaker, p, index=i)
        dur = probe_duration(p)
        out.append(Utterance(i, line.speaker, line.text, p, dur, load_words(p, line.text, dur)))
    return out
