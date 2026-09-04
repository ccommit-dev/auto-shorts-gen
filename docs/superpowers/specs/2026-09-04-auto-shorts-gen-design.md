# auto-shorts-gen 설계 스펙 (2026-09-04)

## 목적
강아지/고양이가 사람처럼 행동하는 코믹 AI 쇼츠(15초 내외, 9:16)를 주제 하나로 자동 생성하고,
계정/권한만 설정하면 유튜브 쇼츠·인스타 릴스에 자동 배포하는 Python CLI.

참고 스타일: 한 장면, 한 캐릭터, 인터뷰형 4~6줄 대사, 마지막 줄 반전, 상단 형광 제목,
하단 굵은 자막이 대사에 맞춰 바뀜, 음성 더빙.

## 비용 원칙 (최우선 제약)
- 기본 설정은 **전부 무료**: Gemini 무료 티어(대본·이미지), edge-tts(음성), ffmpeg(모션·합성),
  YouTube Data API / Instagram Graph API(배포, 무료).
- **유료 경로는 기본 차단**. `ALLOW_PAID=true`를 명시하지 않으면 Claude, Kling, ElevenLabs 등
  유료 공급자는 키가 있어도 `PaidProviderBlocked` 예외로 실행을 중단한다.
- Gemini 무료 티어 초과 방지: 로컬 사용량 원장(`output/.usage.json`)에 일자별 호출 수를 기록하고
  `GEMINI_DAILY_TEXT_CAP`(기본 50), `GEMINI_DAILY_IMAGE_CAP`(기본 50)을 넘으면 호출 전에 중단.
  429/RESOURCE_EXHAUSTED 응답은 재시도하지 않고 중단.
- Gemini 키는 **결제가 연결되지 않은 GCP 프로젝트**에서 발급해야 무료 티어가 적용된다.
  `--check`가 이 사실을 안내한다(프로그램이 결제 상태를 직접 확인할 수는 없음).

## 파이프라인
`python main.py --topic "강아지 군밤장사"` (미지정 시 `topics.py`에서 랜덤)

1. **대본 생성** (`shorts/script_gen.py`)
   - 입력: 주제 문자열. 출력: `Script` (title, character, scene_prompt, lines[{speaker, text}],
     hashtags, topic). JSON 스키마 강제.
   - 기본 공급자 `GeminiScriptProvider`(무료). `ClaudeScriptProvider`는 유료 게이트.
2. **장면 이미지** (`shorts/image_gen.py`)
   - `GeminiImageProvider`: scene_prompt로 9:16 이미지 1장 생성 → Pillow로 1080x1920 맞춤.
   - `PlaceholderImageProvider`: 네트워크 없이 그라데이션+텍스트 이미지(dry-run/테스트).
3. **이미지→영상** (`shorts/video_gen.py`)
   - 기본 `KenBurnsVideoProvider`: ffmpeg zoompan으로 총 길이만큼 줌/팬 클립 생성(무료).
   - `LocalClipProvider`: `assets/clips/` 또는 실행 폴더에 사용자가 넣은 mp4가 있으면 우선 사용
     (Kling 웹앱 무료 크레딧으로 손수 만든 클립 활용 경로).
   - `KlingVideoProvider`: 유료 게이트. image-to-video API 호출 후 폴링.
4. **음성** (`shorts/tts.py`)
   - 기본 `EdgeTTSProvider`: 대사 줄마다 mp3 생성, 화자별 목소리(기자/동물) 매핑.
     ffprobe로 길이 측정 → `Cue(start, end, text, speaker)` 타이밍 산출(줄 사이 0.25초 간격).
   - `ElevenLabsTTSProvider`: 유료 게이트.
5. **합성** (`shorts/compose.py`)
   - 자막/제목은 Pillow로 PNG 오버레이 렌더(굵은 글씨+검정 외곽선, 한국어 폰트 `FONT_PATH`,
     기본 Windows 맑은고딕 볼드) → ffmpeg `overlay` + `enable=between(t,a,b)`.
     drawtext/libass 의존 없음.
   - 오디오: 대사 mp3를 타이밍대로 배치(adelay + amix), `assets/bgm/*.mp3` 있으면 -18dB로 믹스.
   - 출력: 1080x1920, h264, aac, 총 길이 = 마지막 큐 종료 + 0.5초 (목표 12~20초).
6. **출력** (`shorts/pipeline.py`)
   - `output/<YYYYMMDD_HHMMSS>_<slug>/` 에 `script.json`, `scene.png`, `motion.mp4`,
     `line_XX.mp3`, `final.mp4`, `meta.txt`(제목/설명/해시태그), `manifest.json`(단계 상태).
   - 단계별 산출물이 있으면 건너뛰는 재개(resume) 지원.
7. **배포** (`shorts/publish/`)
   - `--publish youtube,instagram` 옵션 또는 `.env`의 `AUTO_PUBLISH`.
   - YouTube: OAuth 데스크톱 플로우(`client_secrets.json` → `token.json`), Data API v3 업로드,
     제목/설명에 `#Shorts`, 공개 범위 `YOUTUBE_PRIVACY`(기본 `private`, 검수 후 공개 권장).
   - Instagram: Graph API 릴스 업로드. 공개 URL이 필요하므로 `MediaHost` 인터페이스:
     `CatboxHost`(무료 익명 호스트, opt-in) 또는 `UrlTemplateHost`(사용자 서버). 미설정 시 명확한
     안내와 함께 중단.
   - 배포 결과(URL/ID)는 `manifest.json`에 기록. 실패해도 영상 파일은 남는다.

## CLI
- `--topic`, `--count N`, `--publish`, `--dry-run`(플레이스홀더 공급자, 네트워크 없음),
  `--allow-paid`(환경변수와 동일), `--video-provider {kenburns,local,kling}`,
  `--check`(ffmpeg/폰트/키/모델 목록/사용량 원장 점검), `--resume <run_dir>`.

## 구성 (.env)
GEMINI_API_KEY, GEMINI_TEXT_MODEL, GEMINI_IMAGE_MODEL, GEMINI_DAILY_TEXT_CAP,
GEMINI_DAILY_IMAGE_CAP, ALLOW_PAID, ANTHROPIC_API_KEY, KLING_ACCESS_KEY, KLING_SECRET_KEY,
ELEVENLABS_API_KEY, TTS_VOICE_ANIMAL, TTS_VOICE_REPORTER, FONT_PATH, OUTPUT_DIR,
AUTO_PUBLISH, YOUTUBE_PRIVACY, IG_USER_ID, IG_ACCESS_TOKEN, IG_MEDIA_HOST.

## 오류 처리
- 유료 차단·쿼터 초과·키 누락은 시작 전에 검사해 첫 API 호출 전에 실패시킨다.
- 각 단계는 예외를 `manifest.json`에 기록하고 중단. `--resume`으로 이어서 실행.
- ffmpeg는 PATH 우선, 없으면 `imageio-ffmpeg` 동봉 바이너리 사용.

## 테스트
- pytest 단위 테스트: cost guard, 사용량 원장, Script JSON 파싱, 큐 타이밍 계산,
  오버레이 렌더, ffmpeg 필터 그래프 조립.
- 통합: `--dry-run`으로 네트워크 없이 `final.mp4`가 생성되고 ffprobe로 길이/해상도 검증.

## 범위 밖 (YAGNI)
GUI, 스케줄러, 다중 장면 편집, 립싱크 후처리, 썸네일 생성.
