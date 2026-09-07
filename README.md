# auto-shorts-gen

강아지/고양이가 사람처럼 직업을 연기하는 **AI 코믹 쇼츠(9:16, 15초 내외)** 를 주제 하나로 자동 생성하고,
계정만 설정하면 **유튜브 쇼츠 / 인스타 릴스에 자동 배포**하는 Python CLI.

참고 스타일: [말순이가 장사하는법](https://www.youtube.com/shorts/Ib766UdgKtc) — 한 장면, 한 캐릭터, 인터뷰 대사, 마지막 반전, 상단 형광 제목, 하단 자막.

## 비용 원칙

- **기본 설정은 전부 무료**입니다.

| 단계 | 기본(무료) | 선택(유료, 기본 차단) |
|---|---|---|
| 대본 | Gemini Flash 무료 티어 | Claude (Anthropic API) |
| 장면 이미지 | pollinations.ai (키 불필요) / `assets/images`의 내 파일 | Gemini 이미지 생성 |
| 이미지→영상 | **로컬 GPU AI(LTX-Video, 오픈소스)** / ffmpeg 퍼펫 모션 / `assets/clips`의 내 mp4 | Kling 3.0 API |
| 음성 | edge-tts (한국어 신경망 음성) | ElevenLabs |
| 합성/자막 | ffmpeg (자동 동봉) | - |
| 배포 | YouTube Data API, Instagram Graph API | - |

- 유료 공급자는 키가 있어도 `ALLOW_PAID=true`(또는 `--allow-paid`)가 없으면 **첫 API 호출 전에 중단**됩니다.
- 무료 API도 일일 상한(`GEMINI_DAILY_TEXT_CAP`, `POLLINATIONS_DAILY_CAP`)을 넘으면 중단됩니다. 사용량은 `output/.usage.json`에 기록됩니다.
- Gemini 무료 티어는 **결제가 연결되지 않은 Google Cloud 프로젝트**의 키에만 적용됩니다. 결제를 연결한 프로젝트의 키를 쓰면 과금될 수 있습니다.

## 설치

```bash
py -3.12 -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

```bash
copy .env.example .env
```

`.env`에 `GEMINI_API_KEY`만 넣으면 됩니다. 키 발급: [Google AI Studio](https://aistudio.google.com/apikey) → 결제 미연결 프로젝트에서 API 키 생성.

## 실행

환경 점검:

```bash
.venv\Scripts\python main.py --check
```

네트워크 없이 파이프라인 전체 점검(플레이스홀더 대본/이미지/무음):

```bash
.venv\Scripts\python main.py --dry-run --topic "강아지 군밤장사"
```

실제 생성:

```bash
.venv\Scripts\python main.py --topic "고양이 편의점 알바"
```

랜덤 주제로 3개:

```bash
.venv\Scripts\python main.py --count 3
```

생성 후 바로 배포:

```bash
.venv\Scripts\python main.py --topic "강아지 택시기사" --publish youtube,instagram
```

중단된 실행 이어하기:

```bash
.venv\Scripts\python main.py --resume output\20260904_150000_장사_잘하는법
```

## 출력 구조

```
output/20260904_150000_장사_잘하는법/
  script.json     대본(제목, 캐릭터, 장면 프롬프트, 대사, 해시태그)
  scene.png       장면 이미지 1080x1920
  line_00.mp3 …   대사별 음성
  motion.mp4      모션 클립
  title.png, sub_00.png …   제목/자막 오버레이
  final.mp4       완성본 (1080x1920, h264+aac)
  meta.txt        업로드용 제목/설명/해시태그
  manifest.json   단계 상태, 배포 결과
```

## 강아지가 실제로 움직이게 (무료, NVIDIA GPU)

NVIDIA GPU(16GB VRAM 권장, RTX 5060 Ti에서 확인)가 있으면 오픈소스 **LTX-Video 2B** 모델로 장면 이미지를
실제 영상으로 만듭니다. 비용은 없고 모델 파일(약 24GB)을 처음 한 번 내려받습니다.

```bash
.venv\Scripts\python -m pip install --index-url https://download.pytorch.org/whl/cu128 torch==2.9.1
```

```bash
.venv\Scripts\python -m pip install -r requirements-gpu.txt
```

모델을 미리 받아 두면 첫 실행이 빠릅니다(프로젝트 `models/` 폴더, HF 캐시의 심볼릭 링크 권한 문제를 피함):

```bash
.venv\Scripts\python scripts\download_models.py
```

- `--video-provider auto`(기본)는 GPU + diffusers가 있으면 자동으로 `ltx`를 씁니다. 강제하려면 `--video-provider ltx`.
- RTX 5060 Ti 16GB 기준 영상 1개에 약 7분(모델 로드 1분 + 생성 2분 + 합성). VRAM 약 11.5GB.
- RTX 50 시리즈에서는 cuDNN 어텐션이 매우 느리거나 CUDA 오류를 내므로 `LTX_ATTENTION_BACKEND=_native_efficient`가 기본입니다. VRAM이 넘치면 Windows가 시스템 RAM으로 넘겨 수십 배 느려지니 `LTX_WIDTH/HEIGHT/NUM_FRAMES`를 줄이세요.
- 생성 설정은 `.env`의 `LTX_MODEL`, `LTX_WIDTH/HEIGHT`(32의 배수), `LTX_NUM_FRAMES`(8k+1), `LTX_STEPS`, `LTX_GUIDANCE`, `LTX_SEED`.
- **말하는 클립, 듣는 클립, 펀치라인용 클로즈업 클립**을 각각 생성(기본 161프레임 ≈ 6.7초, 40스텝)하고, 자막 타이밍대로 잘라 붙입니다. 역재생은 쓰지 않습니다.
- 컷마다 클립을 0초부터 재생해 첫 프레임(같은 장면 이미지)이 이어지고, 0.15초 크로스페이드로 남은 차이를 감춥니다. 0.4초 미만 구간은 이웃에 합칩니다.
- `LTX_SEEDS=2`: 시드를 여러 개 만들어 움직임 점수(연속 프레임 평균 차이)가 목표(말하기 2.5, 듣기 1.0)에 가장 가까운 클립을 자동 선택합니다. `LTX_INTERPOLATE=true`: 24fps→30fps 보간. `LTX_CLOSEUP=true`: 펀치라인에 얼굴 클로즈업 컷.
- 이 설정으로 RTX 5060 Ti 기준 영상 1개에 약 20분(클립 5개 생성). 빠르게 보려면 `LTX_SEEDS=1 LTX_CLOSEUP=false LTX_NUM_FRAMES=97 LTX_STEPS=30`.
- `assets/clips`에 직접 넣을 때도 파일명에 `listen`이 들어간 mp4를 듣는 클립으로 씁니다(없으면 하나로 둘 다).
- GPU가 없으면 `kenburns`가 대신 동작합니다. 이때도 동물 대사 구간에서만 통통 튀는 퍼펫 모션이 들어가 누가 말하는지 보입니다.

## 자막·연출

- 자막은 edge-tts가 주는 어절별 시각(WordBoundary)에 맞춰 **어절이 하나씩 나타납니다**. 단어 타이밍이 없는 음성(ElevenLabs, dry-run)은 글자 수 비례로 균등 배치합니다.
- 마지막 줄(펀치라인)은 앞에 0.5초 뜸을 두고, 노란색 큰 자막 + 화면 8% 줌인 + "띠링" 효과음으로 강조합니다. 제목은 0.25초 팝인, 마지막 0.5초는 정지 프레임.
- 소리: 대사에 가벼운 리버브, 컷마다 작은 "톡" 효과음, 전체 `loudnorm`(-16 LUFS). 줄마다 rate/pitch를 조금씩 바꿔 TTS 단조로움을 줄입니다. 기자 기본 음성은 `ko-KR-HyunsuMultilingualNeural`.
- BGM: `assets/bgm`에 mp3를 넣으면 그걸 쓰고, 없으면 numpy로 합성한 저작권 없는 기본 루프(`default_bgm.mp3`)를 자동 생성합니다. 효과음도 `assets/sfx`에 자동 생성됩니다.
- 장면 이미지: `IMAGE_SEED`로 같은 캐릭터를 재현하고, `IMAGE_STYLE_SUFFIX`(기본 "mouth closed, looking at the camera …")가 프롬프트 뒤에 붙어 입을 다문 정면 얼굴을 유도합니다.
- 합성만 다시 하려면 `--resume <폴더> --redo overlays,compose` (타이밍이 바뀌면 `motion`도 포함).

## 내 소재 쓰기 (무료로 품질 올리기)

- `assets/images/`에 png/jpg를 넣으면 그 이미지를 장면으로 씁니다 (예: Google AI Studio에서 무료로 만든 이미지).
- `assets/clips/`에 mp4를 넣으면 그 클립을 모션 영상으로 씁니다 (예: Kling 웹앱 일일 무료 크레딧으로 만든 image-to-video 클립).
- `assets/bgm/`에 mp3를 넣으면 배경음악으로 낮게 깔립니다.

## 유튜브 자동 업로드 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성 → **YouTube Data API v3** 활성화.
2. OAuth 동의 화면 구성(외부, 테스트 사용자에 본인 계정 추가) → 사용자 인증 정보 → **OAuth 클라이언트 ID(데스크톱 앱)** 생성 → JSON 다운로드 → 프로젝트 루트에 `client_secrets.json`으로 저장.
3. 첫 `--publish youtube` 실행 시 브라우저가 열리고 승인하면 `token.json`이 저장됩니다. 이후는 자동.
4. 기본 공개 범위는 `YOUTUBE_PRIVACY=private`입니다. 검수 후 `public`으로 바꾸세요. 업로드 자체는 무료지만 API 일일 쿼터(10,000 유닛, 업로드 1건 1,600 유닛)가 있습니다.

## 인스타그램 릴스 자동 업로드 설정

1. 인스타 계정을 **비즈니스/크리에이터**로 전환하고 Facebook 페이지와 연결.
2. [Meta for Developers](https://developers.facebook.com/)에서 앱 생성 → Instagram Graph API 추가 → `instagram_basic`, `instagram_content_publish`, `pages_show_list` 권한의 **장기 사용자 액세스 토큰** 발급.
3. `.env`에 `IG_USER_ID`(인스타 비즈니스 계정 ID), `IG_ACCESS_TOKEN` 입력.
4. 릴스 API는 **공개 URL**로만 영상을 받습니다. 둘 중 하나를 설정하세요.
   - `IG_MEDIA_HOST=catbox`: catbox.moe 무료 익명 호스팅에 올린 뒤 그 URL을 사용.
   - `IG_MEDIA_HOST=copydir` + `IG_COPYDIR_PATH`, `IG_COPYDIR_BASE_URL`: 내 웹서버 공개 폴더로 복사.

## 유료 공급자 켜기 (선택)

`.env`에 `ALLOW_PAID=true`와 해당 키를 넣고 옵션으로 지정합니다. 비용이 실제로 발생합니다.

```bash
.venv\Scripts\python main.py --topic "강아지 군밤장사" --video-provider kling --tts-provider elevenlabs --allow-paid
```

## 테스트

```bash
.venv\Scripts\python -m pytest -q
```

네트워크가 필요한 테스트는 없습니다.

## 문제 해결

- **SSL 인증서 오류**(사내망): 기본값 `USE_OS_TRUSTSTORE=true`가 Windows 인증서 저장소를 사용합니다. 그래도 실패하면 `truststore` 설치 여부를 확인하세요.
- **한글 자막이 네모로 나옴**: `FONT_PATH`를 한글 폰트 경로로 지정하세요 (기본 맑은 고딕 볼드).
- **`QuotaExceeded`**: 오늘 무료 상한 도달. 내일 재시도하거나 `.env`의 상한을 조정하세요.
- **`PaidProviderBlocked`**: 유료 공급자를 지정했는데 `ALLOW_PAID`가 꺼져 있습니다. 의도한 것이면 켜세요.
- **Gemini 429 / RESOURCE_EXHAUSTED**: 무료 티어 분당/일일 한도. 잠시 후 재시도.
