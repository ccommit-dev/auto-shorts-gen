from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("cover", "statement", "ui", "chat", "stat", "outro")
MIN_SCENES, MAX_SCENES = 3, 24


class SceneValidationError(ValueError):
    pass


def plain(text: str) -> str:
    """제목 표기에서 마크업을 걷어낸 읽기용 문자열. '||'는 줄바꿈, '[]'는 강조."""
    return re.sub(r"[\[\]]", "", (text or "").replace("||", " ")).strip()


@dataclass
class Scene:
    kind: str = "statement"
    eyebrow: str = ""          # 상단 작은 라벨
    title: str = ""            # 큰 문장. '||' 줄바꿈, '[단어]' 강조색
    body: str = ""             # 보조 설명 한 줄
    narration: str = ""        # 비우면 title+body 를 읽는다
    items: list[dict] = field(default_factory=list)
    hold: float = 0.6          # 나레이션이 끝난 뒤 머무는 시간(초)

    def speech(self) -> str:
        if self.narration.strip():
            return self.narration.strip()
        return " ".join(x for x in (plain(self.title), self.body.strip()) if x)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "eyebrow": self.eyebrow, "title": self.title, "body": self.body,
                "narration": self.narration, "items": self.items, "hold": self.hold}

    @classmethod
    def from_dict(cls, d: dict) -> "Scene":
        return cls(kind=str(d.get("kind", "statement")).lower(), eyebrow=str(d.get("eyebrow", "")),
                   title=str(d.get("title", "")), body=str(d.get("body", "")),
                   narration=str(d.get("narration", "")), items=list(d.get("items") or []),
                   hold=float(d.get("hold", 0.6)))


@dataclass
class PromoScript:
    topic: str
    title: str
    subtitle: str = ""
    accent: str = "#1F7A45"
    scenes: list[Scene] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)

    def validate(self) -> "PromoScript":
        if not self.title.strip():
            raise SceneValidationError("title 이 비었습니다.")
        if not MIN_SCENES <= len(self.scenes) <= MAX_SCENES:
            raise SceneValidationError(f"장면 수는 {MIN_SCENES}~{MAX_SCENES}개여야 합니다 (현재 {len(self.scenes)}).")
        for i, s in enumerate(self.scenes):
            if s.kind not in KINDS:
                raise SceneValidationError(f"{i}번 장면의 kind '{s.kind}' 를 모릅니다. {KINDS} 중 하나여야 합니다.")
            if s.kind in ("ui", "chat", "stat") and not s.items:
                raise SceneValidationError(f"{i}번 장면({s.kind})에 items 가 없습니다.")
            if not s.speech():
                raise SceneValidationError(f"{i}번 장면에 읽을 내용이 없습니다.")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.accent):
            raise SceneValidationError(f"accent 는 '#RRGGBB' 형식이어야 합니다 (현재 {self.accent!r}).")
        return self

    def to_dict(self) -> dict:
        return {"topic": self.topic, "title": self.title, "subtitle": self.subtitle, "accent": self.accent,
                "scenes": [s.to_dict() for s in self.scenes], "hashtags": self.hashtags}

    @classmethod
    def from_dict(cls, d: dict) -> "PromoScript":
        return cls(topic=str(d.get("topic", "")), title=str(d.get("title", "")),
                   subtitle=str(d.get("subtitle", "")), accent=str(d.get("accent", "#1F7A45")),
                   scenes=[Scene.from_dict(x) for x in (d.get("scenes") or [])],
                   hashtags=[str(x) for x in (d.get("hashtags") or [])]).validate()

    @classmethod
    def from_json(cls, text: str) -> "PromoScript":
        raw = text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw)
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise SceneValidationError("JSON 객체를 찾지 못했습니다.")
        return cls.from_dict(json.loads(raw[start:end + 1]))

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), "utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "PromoScript":
        return cls.from_dict(json.loads(Path(path).read_text("utf-8")))
