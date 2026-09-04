from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WordCue:
    start: float
    end: float
    text: str


@dataclass
class Cue:
    start: float
    end: float
    text: str
    speaker: str
    words: list[WordCue] = field(default_factory=list)  # 절대 시각
    punch: bool = False  # 마지막 줄(펀치라인)


def even_words(text: str, duration: float) -> list[tuple[float, float, str]]:
    """단어 타이밍이 없을 때 어절을 글자 수 비례로 균등 배치 (mp3 기준 상대 시각)."""
    words = text.split()
    if not words:
        return []
    total_chars = sum(len(w) for w in words)
    out, t = [], 0.0
    for w in words:
        d = duration * len(w) / total_chars
        out.append((round(t, 3), round(t + d, 3), w))
        t += d
    return out


def build_cues(durations, texts, speakers, gap: float = 0.25, lead_in: float = 0.6,
               words: list[list[tuple[float, float, str]]] | None = None, punch_gap: float = 0.5) -> list[Cue]:
    """대사 길이를 순서대로 배치해 자막/음성 타이밍을 만든다.

    words: 줄별 (start, end, text) 상대 시각. 없으면 균등 분배.
    마지막 줄 앞에는 punch_gap 만큼 뜸을 더 둬 반전이 살도록 한다.
    """
    n = len(durations)
    cues, t = [], lead_in
    for i, (d, text, sp) in enumerate(zip(durations, texts, speakers)):
        last = i == n - 1
        if last and n > 1:
            t += punch_gap
        rel = (words[i] if words and i < len(words) and words[i] else None) or even_words(text, d)
        abs_words = [WordCue(round(t + ws, 3), round(t + we, 3), w) for ws, we, w in rel]
        cues.append(Cue(round(t, 3), round(t + d, 3), text, sp, abs_words, punch=last))
        t += d + gap
    return cues


def total_duration(cues: list[Cue], tail: float = 0.6) -> float:
    return round((cues[-1].end if cues else 0.0) + tail, 3)
