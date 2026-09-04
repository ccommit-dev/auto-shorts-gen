from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .config import Settings
from .cost_guard import ensure_allowed
from .ffmpeg_tools import make_silence, probe_duration
from .script_model import Script


@dataclass
class Utterance:
    index: int
    speaker: str
    text: str
    path: Path
    duration: float


class TTSProvider(Protocol):
    def synthesize(self, text: str, speaker: str, out_path: Path) -> Path: ...


class EdgeTTSProvider:
    """Microsoft Edge 신경망 음성 (무료)."""
    name = "edge-tts"

    def __init__(self, settings: Settings):
        ensure_allowed(self.name, settings.allow_paid)
        self.voices = {"animal": settings.tts_voice_animal, "reporter": settings.tts_voice_reporter}

    def synthesize(self, text: str, speaker: str, out_path: Path) -> Path:
        import edge_tts
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rate = "+8%" if speaker == "animal" else "+0%"
        pitch = "+20Hz" if speaker == "animal" else "+0Hz"
        voice = self.voices.get(speaker, self.voices["animal"])
        edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save_sync(str(out_path))
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

    def synthesize(self, text: str, speaker: str, out_path: Path) -> Path:
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

    def synthesize(self, text: str, speaker: str, out_path: Path) -> Path:
        return make_silence(out_path, 0.5 + 0.12 * len(text))


def synthesize_lines(script: Script, provider: TTSProvider, path_for: Callable[[int], Path]) -> list[Utterance]:
    out = []
    for i, line in enumerate(script.lines):
        p = Path(path_for(i))
        if not p.exists():
            provider.synthesize(line.text, line.speaker, p)
        out.append(Utterance(i, line.speaker, line.text, p, probe_duration(p)))
    return out
