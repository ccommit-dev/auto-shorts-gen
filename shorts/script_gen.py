from __future__ import annotations

from typing import Protocol

from .config import Settings
from .cost_guard import ensure_allowed
from .script_model import SCRIPT_JSON_SCHEMA, Line, Script
from .usage_ledger import UsageLedger

SYSTEM_PROMPT = """너는 한국 유튜브 쇼츠 '#ai동물영상' 장르의 대본 작가다.
형식: 강아지나 고양이 한 마리가 사람처럼 직업/상황을 연기하고, 기자(reporter)가 인터뷰한다.
규칙:
- 대사 3~6줄, 전체 15초 안에 읽힐 분량(줄당 14자 이내 권장, 최대 25자).
- 마지막 줄은 반드시 반전/펀치라인. 예: "예쁜 언니 천원, 못생긴 언니 오백원".
- speaker는 "reporter" 또는 "animal"만 사용. 첫 줄은 reporter 질문.
- title은 8~12자 짧은 훅(예: "장사 잘하는법").
- character는 품종/색/소품 한 줄. scene_prompt는 영어로: photorealistic, vertical 9:16,
  the animal wearing the job outfit, doing the job, being interviewed with a microphone, cinematic lighting.
- hashtags 4~6개, 한국어, '#ai동물영상' 포함.
반드시 JSON 객체 하나만 출력한다."""


def build_user_prompt(topic: str) -> str:
    return f"주제: {topic}\n위 규칙대로 JSON을 만들어라."


class ScriptProvider(Protocol):
    def generate(self, topic: str) -> Script: ...


class GeminiScriptProvider:
    """Gemini Flash 무료 티어 (결제 미연결 프로젝트 키)."""
    name = "gemini-text"

    def __init__(self, settings: Settings, ledger: UsageLedger):
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY가 없습니다. .env에 설정하거나 --dry-run을 쓰세요.")
        self.s, self.ledger = settings, ledger

    def generate(self, topic: str) -> Script:
        ensure_allowed(self.name, self.s.allow_paid)
        self.ledger.reserve(self.name, self.s.gemini_daily_text_cap)
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=self.s.gemini_api_key)
        resp = client.models.generate_content(
            model=self.s.gemini_text_model,
            contents=build_user_prompt(topic),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_json_schema=SCRIPT_JSON_SCHEMA,
                temperature=1.0,
            ),
        )
        return Script.from_json(resp.text or "", topic=topic)


class ClaudeScriptProvider:
    """Anthropic API (유료, ALLOW_PAID 필요)."""
    name = "claude"

    def __init__(self, settings: Settings):
        ensure_allowed(self.name, settings.allow_paid)
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY가 없습니다.")
        self.s = settings

    def generate(self, topic: str) -> Script:
        import anthropic
        client = anthropic.Anthropic(api_key=self.s.anthropic_api_key)
        resp = client.messages.create(
            model=self.s.claude_model, max_tokens=2000, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(topic)}],
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("Claude가 요청을 거절했습니다")
        text = "".join(b.text for b in resp.content if b.type == "text")
        return Script.from_json(text, topic=topic)


class PlaceholderScriptProvider:
    """네트워크 없이 쓰는 고정 샘플 대본 (dry-run)."""
    name = "placeholder"

    def generate(self, topic: str) -> Script:
        return Script(
            topic=topic, title="장사 잘하는법", character="하얀 비숑 말순이, 군밤장수 모자",
            scene_prompt=("photorealistic vertical 9:16 photo of a fluffy white bichon frise dog wearing a vendor hat, "
                          "selling roasted chestnuts at a korean night street stall, holding tongs, "
                          "being interviewed with a microphone, warm cinematic lighting"),
            lines=[Line("reporter", "군밤 얼마예요?"), Line("animal", "예쁜 언니 천원"),
                   Line("animal", "못생긴 언니 오백원"), Line("reporter", "저는요?"),
                   Line("animal", "내가 살게 이천원")],
            hashtags=["#ai동물영상", "#ai쇼츠", "#강아지", "#웃긴영상"],
        ).validate()
