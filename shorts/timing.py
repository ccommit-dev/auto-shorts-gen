from dataclasses import dataclass


@dataclass
class Cue:
    start: float
    end: float
    text: str
    speaker: str


def build_cues(durations, texts, speakers, gap: float = 0.25, lead_in: float = 0.6) -> list[Cue]:
    """대사 길이를 순서대로 배치해 자막/음성 타이밍을 만든다."""
    cues, t = [], lead_in
    for d, text, sp in zip(durations, texts, speakers):
        cues.append(Cue(round(t, 3), round(t + d, 3), text, sp))
        t += d + gap
    return cues


def total_duration(cues: list[Cue], tail: float = 0.6) -> float:
    return round((cues[-1].end if cues else 0.0) + tail, 3)
