from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

SPEAKERS = ("reporter", "animal")


@dataclass
class Line:
    speaker: str
    text: str


@dataclass
class Script:
    topic: str
    title: str
    character: str
    scene_prompt: str
    lines: list[Line]
    hashtags: list[str] = field(default_factory=list)

    def validate(self) -> "Script":
        self.title = self.title.strip()[:20]
        if not self.title:
            raise ValueError("title이 비었습니다")
        if not (3 <= len(self.lines) <= 6):
            raise ValueError(f"대사는 3~6줄이어야 합니다 (현재 {len(self.lines)})")
        for l in self.lines:
            l.speaker = l.speaker if l.speaker in SPEAKERS else "animal"
            l.text = " ".join(l.text.split())[:40]
            if not l.text:
                raise ValueError("빈 대사가 있습니다")
        self.hashtags = [h if h.startswith("#") else "#" + h
                         for h in (t.strip() for t in self.hashtags) if h]
        if not self.hashtags:
            self.hashtags = ["#ai동물영상", "#ai쇼츠"]
        if not self.scene_prompt.strip():
            raise ValueError("scene_prompt가 비었습니다")
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict, topic: str | None = None) -> "Script":
        lines = [Line(str(x.get("speaker", "animal")), str(x.get("text", ""))) for x in d.get("lines", [])]
        return cls(topic=topic or str(d.get("topic", "")), title=str(d.get("title", "")),
                   character=str(d.get("character", "")), scene_prompt=str(d.get("scene_prompt", "")),
                   lines=lines, hashtags=[str(h) for h in d.get("hashtags", [])]).validate()

    @classmethod
    def from_json(cls, text: str, topic: str | None = None) -> "Script":
        t = text.strip()
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
        start, end = t.find("{"), t.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("JSON 객체를 찾지 못했습니다")
        return cls.from_dict(json.loads(t[start:end + 1]), topic=topic)


SCRIPT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "상단 제목, 12자 이내"},
        "character": {"type": "string", "description": "캐릭터 외형/이름 한 줄"},
        "scene_prompt": {"type": "string", "description": "영어 이미지 프롬프트, photorealistic, vertical"},
        "lines": {"type": "array", "minItems": 3, "maxItems": 6,
                  "items": {"type": "object",
                            "properties": {"speaker": {"type": "string", "enum": ["reporter", "animal"]},
                                           "text": {"type": "string"}},
                            "required": ["speaker", "text"]}},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "character", "scene_prompt", "lines", "hashtags"],
}


def slugify(text: str, max_len: int = 30) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_")
    return s[:max_len].rstrip("_") or "shorts"
