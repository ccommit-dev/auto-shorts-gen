"""제품 소개 영상 대본(장면 구성) 생성기. 기본은 Gemini 무료 티어, 키가 없으면 플레이스홀더."""
from __future__ import annotations

from typing import Protocol

from ..config import Settings
from ..cost_guard import ensure_allowed
from ..usage_ledger import UsageLedger
from .spec import PromoScript, Scene

SYSTEM_PROMPT = """너는 B2B 제품 소개 영상의 구성 작가다. 정보형 모션 그래픽 영상의 장면 목록을 만든다.
형식: JSON 객체 하나만 출력한다.

스키마:
{"topic":str,"title":str,"subtitle":str,"accent":"#RRGGBB",
 "scenes":[{"kind":str,"eyebrow":str,"title":str,"body":str,"narration":str,"items":[...],"hold":float}],
 "hashtags":[str]}

kind 는 다음 6가지만 쓴다.
- cover   : 첫 장면. 제품 이름과 한 줄 선언.
- statement: 메시지 한 문장. 가장 많이 쓰는 장면.
- ui      : 왼쪽 메시지 + 오른쪽 UI 카드 3개. items=[{"title":str,"sub":str,"state":"켜짐"|"꺼짐"}]
- chat    : 왼쪽 메시지 + 오른쪽 대화창. items=[{"from":"them"|"me","text":str}] 2~4개.
- stat    : 숫자 3개. items=[{"value":"3,743","unit":"건","label":"설명"}]
- outro   : 마지막 장면. 한 줄 마무리.

규칙:
- 장면 8~14개. 첫 장면은 cover, 마지막은 outro. ui/chat/stat 을 최소 한 번씩 섞는다.
- title 은 화면에 크게 박히는 문장이다. 12~26자. '||' 로 줄을 나누고, 강조할 단어는 '[단어]' 로 감싼다.
  강조는 장면당 1~2곳만. 예: "좋은 지식은||중앙에 쌓이고,||[스킬]로 강해집니다."
- body 는 없거나 한 줄(40자 이내). narration 은 그 장면에서 읽어줄 말(40~70자, 문장 1~2개).
  narration 은 title 을 그대로 읽지 말고 자연스러운 설명체로 쓴다.
- eyebrow 는 그 장면의 소제목 8자 내외.
- 과장 광고 문구를 쓰지 않는다. 기능과 쓸모를 담담하게 말한다.
- accent 는 제품 분위기에 맞는 진한 색 하나.
반드시 JSON 객체 하나만 출력한다."""

PROMO_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "accent": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["cover", "statement", "ui", "chat", "stat", "outro"]},
                    "eyebrow": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "narration": {"type": "string"},
                    "hold": {"type": "number"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"}, "sub": {"type": "string"},
                                "state": {"type": "string"}, "from": {"type": "string"},
                                "text": {"type": "string"}, "value": {"type": "string"},
                                "unit": {"type": "string"}, "label": {"type": "string"},
                            },
                        },
                    },
                },
                "required": ["kind", "title"],
            },
        },
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "scenes"],
}


class PromoScriptProvider(Protocol):
    def generate(self, brief: str) -> PromoScript: ...


class GeminiPromoScript:
    """Gemini Flash 무료 티어."""
    name = "gemini-text"

    def __init__(self, settings: Settings, ledger: UsageLedger):
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY가 없습니다. .env에 설정하거나 --dry-run을 쓰세요.")
        self.s, self.ledger = settings, ledger

    def generate(self, brief: str) -> PromoScript:
        ensure_allowed(self.name, self.s.allow_paid)
        self.ledger.reserve(self.name, self.s.gemini_daily_text_cap)
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=self.s.gemini_api_key)
        resp = client.models.generate_content(
            model=self.s.gemini_text_model,
            contents=f"소개할 제품/서비스: {brief}\n위 규칙대로 JSON을 만들어라.",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT, response_mime_type="application/json",
                response_json_schema=PROMO_JSON_SCHEMA, temperature=0.9),
        )
        script = PromoScript.from_json(resp.text or "")
        script.topic = script.topic or brief
        return script


class PlaceholderPromoScript:
    """네트워크/키 없이 전체 흐름을 확인하는 기본 구성."""
    name = "placeholder"

    def generate(self, brief: str) -> PromoScript:
        b = brief.strip() or "우리 제품"
        return PromoScript(
            topic=b, title=b, subtitle="하루를 바꾸는 작은 도구", accent="#1F7A45",
            hashtags=["#제품소개", "#모션그래픽"],
            scenes=[
                Scene("cover", "제품 소개", f"[{b}]가||일을 거듭니다.", "매일 쓰는 도구를 다시 설계했습니다.",
                      f"{b}를 소개합니다. 매일 쓰는 도구를 처음부터 다시 설계했습니다."),
                Scene("statement", "왜 만들었나", "흩어진 기록은||[아무도] 찾지 않습니다.", "폴더에 쌓인 문서는 검색되지 않습니다.",
                      "흩어진 기록은 결국 아무도 찾지 않습니다. 폴더에 쌓인 문서는 검색되지 않으니까요."),
                Scene("chat", "묻고 답하기", "물어보면||[바로] 답합니다.", "", "궁금한 것을 물어보면 바로 답합니다.",
                      items=[{"from": "me", "text": "지난주 회의 결론이 뭐였죠?"},
                             {"from": "them", "text": "출시일을 2주 미루고, 검수 범위를 줄이기로 했습니다."},
                             {"from": "me", "text": "근거 문서도 같이 줘요"}]),
                Scene("ui", "어디서나", "쓰던 자리에서||[그대로] 씁니다.", "설치한 기기에서 바로 켜집니다.",
                      "쓰던 자리에서 그대로 씁니다. 설치한 기기에서 바로 켜집니다.",
                      items=[{"title": "지민의 노트북", "sub": "팀 스킬, 문서 점검", "state": "켜짐"},
                             {"title": "도윤의 데스크톱", "sub": "회의록 자동 정리", "state": "켜짐"},
                             {"title": "서연의 태블릿", "sub": "읽기 전용", "state": "꺼짐"}]),
                Scene("stat", "지금까지", "쌓인 만큼||[빨라집니다].", "", "쓰면 쓸수록 쌓이고, 쌓인 만큼 빨라집니다.",
                      items=[{"value": "3,743", "unit": "건", "label": "정리된 기록"},
                             {"value": "21", "unit": "개", "label": "연결된 채널"},
                             {"value": "120", "unit": "일", "label": "함께한 기간"}]),
                Scene("outro", "", f"[{b}]와||내일부터.", "오늘 바로 시작할 수 있습니다.",
                      "지금 바로 시작할 수 있습니다. 내일의 일이 조금 가벼워집니다."),
            ],
        ).validate()


def build_promo_script_provider(settings: Settings, ledger: UsageLedger, *, dry_run: bool,
                                provider: str | None = None) -> PromoScriptProvider:
    name = (provider or ("placeholder" if dry_run else "gemini")).lower()
    if name == "placeholder" or dry_run:
        return PlaceholderPromoScript()
    if name == "gemini":
        return GeminiPromoScript(settings, ledger)
    raise RuntimeError(f"promo 대본 공급자 '{name}' 를 모릅니다 (gemini | placeholder).")
