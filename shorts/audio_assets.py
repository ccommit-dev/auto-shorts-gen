"""무료·저작권 걱정 없는 효과음/기본 BGM 을 numpy 로 합성해 assets 에 만들어 둔다.

- assets/sfx/ding.wav : 펀치라인용 "띠링" (두 음 종소리)
- assets/sfx/pop.wav  : 컷 전환용 아주 작은 "톡"
- assets/bgm/default_bgm.mp3 : 잔잔한 마림바풍 아르페지오 루프 (사용자 BGM 이 있으면 쓰지 않음)
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

from .ffmpeg_tools import run_ffmpeg

SR = 44100


def _write_wav(path: Path, samples: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(samples, -1.0, 1.0)
    data = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return path


def _tone(freq: float, seconds: float, decay: float = 6.0, harmonics=(1.0, 0.35, 0.12)) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    env = np.exp(-decay * t)
    sig = sum(a * np.sin(2 * math.pi * freq * (k + 1) * t) for k, a in enumerate(harmonics))
    return (sig * env).astype(np.float32)


def make_ding(path: Path) -> Path:
    """E6 → A6 두 음, 0.85초."""
    a = _tone(1318.5, 0.5, decay=5)
    b = _tone(1760.0, 0.7, decay=4)
    out = np.zeros(int(SR * 0.85), np.float32)
    out[:len(a)] += a * 0.6
    out[int(SR * 0.12):int(SR * 0.12) + len(b)] += b * 0.6
    return _write_wav(path, out)


def make_pop(path: Path) -> Path:
    """짧은 필터 노이즈 '톡', 0.08초."""
    n = int(SR * 0.08)
    rng = np.random.default_rng(3)
    noise = rng.standard_normal(n).astype(np.float32)
    env = np.exp(-60 * np.arange(n) / SR)
    # 간단한 저역 통과(이동 평균)로 부드럽게
    kernel = np.ones(24, np.float32) / 24
    soft = np.convolve(noise, kernel, mode="same")
    return _write_wav(path, soft * env * 0.5)


def make_bgm(path: Path, seconds: float = 24.0, bpm: float = 96.0) -> Path:
    """C - Am - F - G 진행의 8분음표 아르페지오. 마림바 느낌의 짧은 감쇠음."""
    chords = [(261.6, 329.6, 392.0, 523.3), (220.0, 261.6, 329.6, 440.0),
              (174.6, 220.0, 261.6, 349.2), (196.0, 246.9, 293.7, 392.0)]
    step = 60.0 / bpm / 2  # 8분음표
    total = int(SR * seconds)
    out = np.zeros(total, np.float32)
    pattern = [0, 1, 2, 3, 2, 1, 0, 2]
    i = 0
    t = 0.0
    while t < seconds:
        chord = chords[(i // 8) % len(chords)]
        freq = chord[pattern[i % 8]]
        note = _tone(freq, 0.45, decay=7, harmonics=(1.0, 0.2, 0.05)) * 0.35
        start = int(t * SR)
        end = min(total, start + len(note))
        out[start:end] += note[:end - start]
        t += step
        i += 1
    # 루프 경계 클릭 방지: 앞뒤 50ms 페이드
    fade = int(SR * 0.05)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    wav = path.with_suffix(".wav")
    _write_wav(wav, out)
    path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-i", str(wav), "-c:a", "libmp3lame", "-q:a", "4", str(path)])
    wav.unlink(missing_ok=True)
    return path


def ensure_audio_assets(assets_dir: str | Path) -> dict[str, Path]:
    """없으면 만들고 경로를 돌려준다. bgm 은 사용자가 넣은 파일이 우선."""
    assets = Path(assets_dir)
    sfx = assets / "sfx"
    ding, pop = sfx / "ding.wav", sfx / "pop.wav"
    if not ding.exists():
        make_ding(ding)
    if not pop.exists():
        make_pop(pop)
    bgm_dir = assets / "bgm"
    user_bgm = sorted(p for p in bgm_dir.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav")
                      and p.name != "default_bgm.mp3") if bgm_dir.exists() else []
    bgm = user_bgm[0] if user_bgm else bgm_dir / "default_bgm.mp3"
    if not bgm.exists():
        make_bgm(bgm)
    return {"ding": ding, "pop": pop, "bgm": bgm}
