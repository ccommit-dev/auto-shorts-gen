from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderInfo:
    free: bool
    note: str = ""


PROVIDERS: dict[str, ProviderInfo] = {
    "gemini-text": ProviderInfo(True, "Gemini Flash 무료 티어(결제 미연결 프로젝트)"),
    "pollinations": ProviderInfo(True, "pollinations.ai 무료 이미지, 키 불필요"),
    "edge-tts": ProviderInfo(True, "Microsoft Edge 신경망 음성"),
    "kenburns": ProviderInfo(True, "ffmpeg 줌/팬 + 퍼펫 모션"),
    "ltx": ProviderInfo(True, "로컬 GPU 오픈소스 LTX-Video image-to-video"),
    "local": ProviderInfo(True, "사용자가 넣은 파일"),
    "placeholder": ProviderInfo(True, "dry-run"),
    "playwright": ProviderInfo(True, "설치된 브라우저로 로컬 렌더링, 비용 없음"),
    "youtube": ProviderInfo(True, "YouTube Data API 업로드"),
    "instagram": ProviderInfo(True, "Instagram Graph API"),
    "catbox": ProviderInfo(True, "catbox.moe 익명 호스팅"),
    "gemini-image": ProviderInfo(False, "Gemini 이미지 생성은 무료 티어 없음"),
    "claude": ProviderInfo(False, "Anthropic API는 종량제"),
    "kling": ProviderInfo(False, "Kling API 리소스 패키지 필요"),
    "elevenlabs": ProviderInfo(False, "API 무료 티어 사실상 없음"),
}


class PaidProviderBlocked(RuntimeError):
    pass


def ensure_allowed(provider: str, allow_paid: bool) -> None:
    info = PROVIDERS.get(provider, ProviderInfo(False, "미등록 공급자"))
    if info.free or allow_paid:
        return
    raise PaidProviderBlocked(
        f"'{provider}'는 비용이 발생할 수 있어 차단되었습니다 ({info.note}). "
        f"정말 사용하려면 ALLOW_PAID=true 또는 --allow-paid 를 지정하세요."
    )
