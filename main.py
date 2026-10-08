"""auto-shorts-gen: 강아지/고양이 AI 쇼츠 자동 생성 + 배포 CLI (기본 전부 무료)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="auto-shorts-gen",
                                description="강아지/고양이 AI 쇼츠 자동 생성기 (기본 전부 무료, 유료 공급자는 차단)")
    p.add_argument("--mode", choices=["shorts", "promo"], default="shorts",
                   help="shorts=세로 AI 동물 쇼츠(기본), promo=가로 모션 그래픽 제품 소개 영상")
    p.add_argument("--brief", help='promo 모드에서 소개할 제품/서비스 한 줄. 예: "사내 지식 검색 도구 모코"')
    p.add_argument("--topic", help='주제. 예: "강아지 군밤장사" (생략 시 랜덤)')
    p.add_argument("--count", type=int, default=1, help="생성 개수")
    p.add_argument("--publish", default="", help="배포 대상: youtube,instagram (생략 시 .env AUTO_PUBLISH)")
    p.add_argument("--dry-run", action="store_true", help="네트워크 없이 플레이스홀더로 전체 파이프라인 실행")
    p.add_argument("--allow-paid", action="store_true", help="유료 공급자 허용 (기본 차단)")
    p.add_argument("--script-provider", choices=["gemini", "claude", "placeholder"],
                   help="기본 gemini(무료). placeholder는 키 없이 고정 샘플 대본")
    p.add_argument("--image-provider", choices=["pollinations", "gemini", "local", "placeholder"],
                   help="기본 pollinations(무료). assets/images 에 파일이 있으면 local")
    p.add_argument("--tts-provider", choices=["edge", "elevenlabs"], help="기본 edge(무료)")
    p.add_argument("--video-provider", choices=["auto", "kenburns", "local", "ltx", "kling"],
                   help="기본 auto: assets/clips 에 mp4가 있으면 local, NVIDIA GPU가 있으면 ltx(로컬 AI), 아니면 kenburns")
    p.add_argument("--resume", help="기존 실행 폴더를 이어서 실행")
    p.add_argument("--redo", default="",
                   help="--resume 시 다시 할 단계. shorts: image,motion,overlays,compose / promo: frames,audio,poster")
    p.add_argument("--check", action="store_true", help="환경/키/쿼터 점검만 하고 종료")
    p.add_argument("--no-dotenv", action="store_true", help=".env 를 읽지 않음(테스트용)")
    return p


def run_check(settings) -> int:
    from shorts.cost_guard import PROVIDERS
    from shorts.ffmpeg_tools import ffmpeg_exe
    from shorts.overlay import resolve_font
    from shorts.usage_ledger import UsageLedger
    print(f"ffmpeg        : {ffmpeg_exe()}")
    print(f"font          : {resolve_font(settings.font_path) or '(Pillow 기본, 한글 깨질 수 있음)'}")
    print(f"ALLOW_PAID    : {settings.allow_paid}  (false면 유료 공급자 전부 차단)")
    led = UsageLedger(Path(settings.output_dir) / ".usage.json")
    print(f"오늘 사용량    : gemini-text {led.count('gemini-text')}/{settings.gemini_daily_text_cap}, "
          f"pollinations {led.count('pollinations')}/{settings.pollinations_daily_cap}")
    print(f"GEMINI_API_KEY: {'있음' if settings.gemini_api_key else '없음 (대본 생성 불가 → --dry-run 만 가능)'}")
    print("  * Gemini 무료 티어는 결제가 연결되지 않은 Google Cloud 프로젝트의 키에만 적용됩니다.")
    if settings.gemini_api_key:
        try:
            from google import genai
            client = genai.Client(api_key=settings.gemini_api_key)
            names = [m.name for m in client.models.list()]
            ok = any(settings.gemini_text_model in n for n in names)
            print(f"  모델 {settings.gemini_text_model}: {'사용 가능' if ok else '목록에 없음! GEMINI_TEXT_MODEL 확인'}")
        except Exception as e:
            print(f"  Gemini 연결 실패: {e}")
    print(f"promo 영상     : {settings.promo_width}x{settings.promo_height} {settings.promo_fps}fps, "
          f"브라우저 {settings.promo_browser}, 강조색 {settings.promo_accent}")
    try:
        import playwright  # noqa: F401
        pw = "설치됨"
    except ImportError:
        pw = "없음 (pip install playwright)"
    from shorts.promo.fonts import find_font
    font = find_font(settings.assets_dir)
    print(f"  playwright  : {pw}")
    print(f"  한글 폰트    : {font.name if font else '없음 → 맑은 고딕으로 렌더 (scripts/download_fonts.py 권장)'}")
    print(f"YouTube       : secrets {'있음' if Path(settings.youtube_client_secrets).exists() else '없음'}, "
          f"token {'있음' if Path(settings.youtube_token).exists() else '없음'}, privacy={settings.youtube_privacy}")
    print(f"Instagram     : user_id {'있음' if settings.ig_user_id else '없음'}, "
          f"token {'있음' if settings.ig_access_token else '없음'}, host={settings.ig_media_host}")
    print("공급자 표      : " + ", ".join(f"{k}({'무료' if v.free else '유료'})" for k, v in PROVIDERS.items()))
    return 0


def run_promo(settings, args, ledger, publish, clear_steps) -> int:
    """가로 모션 그래픽 제품 소개 영상. 브라우저 렌더 + edge-tts + ffmpeg, 전부 무료."""
    from shorts.promo.pipeline import PromoPaths, run_promo_pipeline
    from shorts.promo.script_gen import build_promo_script_provider
    from shorts.tts import EdgeTTSProvider, ElevenLabsTTSProvider, SilentTTSProvider

    sp = build_promo_script_provider(settings, ledger, dry_run=args.dry_run,
                                     provider=args.script_provider)
    if args.dry_run:
        tts = SilentTTSProvider()
    elif args.tts_provider == "elevenlabs":
        tts = ElevenLabsTTSProvider(settings)
    else:
        tts = EdgeTTSProvider(settings)

    brief = args.brief or args.topic or "우리 제품"
    if args.resume:
        run_dir = Path(args.resume)
        if args.redo:
            clear_steps(PromoPaths(run_dir).manifest_json)
        run_promo_pipeline(settings, tts, sp, brief, run_dir=run_dir, publish=publish)
        return 0
    for i in range(max(1, args.count)):
        print(f"\n=== [promo {i + 1}/{args.count}] {brief} ===")
        run_promo_pipeline(settings, tts, sp, brief, publish=publish)
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔 코드페이지와 무관하게 한글 출력
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    from shorts.config import load_settings
    from shorts.net import enable_os_truststore
    settings = load_settings(None if args.no_dotenv else ".env")
    if args.allow_paid:
        settings.allow_paid = True
    if settings.use_os_truststore:
        enable_os_truststore()
    if args.check:
        return run_check(settings)

    from shorts.pipeline import run_pipeline
    from shorts.providers import build_providers
    from shorts.topics import random_topic
    from shorts.usage_ledger import UsageLedger
    ledger = UsageLedger(Path(settings.output_dir) / ".usage.json")
    publish = tuple(x.strip() for x in args.publish.split(",") if x.strip()) or settings.auto_publish

    def clear_steps(manifest_path: Path) -> None:
        from shorts.pipeline import Manifest
        m = Manifest.load(manifest_path)
        for step in (x.strip() for x in args.redo.split(",") if x.strip()):
            m.data["steps"].pop(step, None)
        m.save()

    if args.mode == "promo":
        try:
            return run_promo(settings, args, ledger, publish, clear_steps)
        except Exception as e:
            print(f"\n중단: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
    try:
        providers = build_providers(settings, dry_run=args.dry_run, video_provider=args.video_provider,
                                    image_provider=args.image_provider, script_provider=args.script_provider,
                                    tts_provider=args.tts_provider, ledger=ledger)
        if args.resume:
            if args.redo:
                from shorts.pipeline import RunPaths
                clear_steps(RunPaths(Path(args.resume)).manifest_json)
            run_pipeline(settings, providers, args.topic or "", run_dir=Path(args.resume), publish=publish)
            return 0
        for i in range(args.count):
            topic = args.topic or random_topic()
            print(f"\n=== [{i + 1}/{args.count}] 주제: {topic} ===")
            run_pipeline(settings, providers, topic, publish=publish)
        return 0
    except Exception as e:
        print(f"\n중단: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
