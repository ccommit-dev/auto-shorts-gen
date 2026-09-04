# auto-shorts-gen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 주제 하나로 강아지/고양이 코믹 AI 쇼츠(9:16, 15초 내외)를 무료 도구만으로 자동 생성하고, 계정 설정 시 유튜브/인스타에 자동 배포하는 Python CLI.

**Architecture:** `shorts/` 패키지에 단계별 모듈(대본 → 이미지 → 음성/타이밍 → 모션 영상 → 오버레이/합성 → 출력 → 배포). 각 단계는 Protocol 기반 공급자(provider)로 교체 가능하며, 유료 공급자는 `cost_guard`가 기본 차단하고 무료 API는 `usage_ledger`가 일일 상한을 강제한다. `pipeline.py`가 실행 폴더와 `manifest.json`으로 단계를 오케스트레이션·재개한다.

**Tech Stack:** Python 3.12 (`.venv`), google-genai, edge-tts, Pillow, imageio-ffmpeg(ffmpeg 7.1 동봉), requests, truststore, python-dotenv, google-api-python-client + google-auth-oauthlib, pytest.

**Spec:** `docs/superpowers/specs/2026-09-04-auto-shorts-gen-design.md`

## Global Constraints

- 기본 설정은 전부 무료. 유료 공급자(claude, gemini-image, kling, elevenlabs)는 `ALLOW_PAID=true`가 아니면 `PaidProviderBlocked`로 첫 API 호출 전에 중단.
- 무료 API 일일 상한: `GEMINI_DAILY_TEXT_CAP=50`, `POLLINATIONS_DAILY_CAP=100`(원장 `output/.usage.json`). 429/RESOURCE_EXHAUSTED는 재시도 없이 중단.
- Gemini 이미지 생성은 공식 가격표상 무료 티어가 없음 → 유료 게이트. 기본 이미지 공급자는 pollinations.ai(키 불필요).
- 출력 규격: 1080x1920, h264 + aac, 30fps, 길이 = 마지막 자막 종료 + 0.6초.
- HTTPS는 `truststore.inject_into_ssl()`로 OS 인증서 저장소 사용(`USE_OS_TRUSTSTORE=true` 기본). 사내망 SSL 검사 대응.
- ffmpeg: PATH 우선, 없으면 `imageio_ffmpeg.get_ffmpeg_exe()`. ffprobe는 동봉되지 않으므로 길이/해상도는 `ffmpeg -i` 출력 파싱.
- 테스트 실행: `.venv/Scripts/python -m pytest -q`. 네트워크가 필요한 테스트는 없다.
- 폰트 기본값 `C:/Windows/Fonts/malgunbd.ttf`(맑은 고딕 볼드), 없으면 `NotoSansKR-VF.ttf`, 그것도 없으면 Pillow 기본 폰트.

---

## File Structure

```
main.py                       CLI 진입점(argparse): run / --check
shorts/__init__.py
shorts/net.py                 truststore 주입
shorts/config.py              Settings(from_env), load_settings
shorts/cost_guard.py          PROVIDERS 표, ensure_allowed, PaidProviderBlocked
shorts/usage_ledger.py        UsageLedger(reserve), QuotaExceeded
shorts/ffmpeg_tools.py        ffmpeg_exe, run_ffmpeg, probe_duration, probe_resolution, make_silence
shorts/script_model.py        Line, Script, SCRIPT_JSON_SCHEMA, slugify
shorts/topics.py              랜덤 주제 목록
shorts/script_gen.py          Gemini/Claude/Placeholder ScriptProvider
shorts/image_gen.py           Pollinations/Gemini/Local/Placeholder ImageProvider, fit_portrait
shorts/tts.py                 EdgeTTS/ElevenLabs/Silent TTSProvider, synthesize_lines, Utterance
shorts/timing.py              Cue, build_cues, total_duration
shorts/video_gen.py           KenBurns/LocalClip/Kling VideoProvider
shorts/overlay.py             render_title, render_subtitle (Pillow PNG)
shorts/compose.py             build_compose_command, compose
shorts/providers.py           Providers 묶음, build_providers
shorts/pipeline.py            RunPaths, Manifest, run_pipeline
shorts/publish/__init__.py    publish_all
shorts/publish/youtube.py     get_credentials, build_video_body, upload_short
shorts/publish/media_host.py  MediaHost, CopyDirHost, CatboxHost
shorts/publish/instagram.py   publish_reel
tests/…                       모듈별 단위 테스트 + dry-run 통합
requirements.txt, .env.example, .gitignore, README.md
assets/bgm/.gitkeep, assets/clips/.gitkeep, assets/images/.gitkeep
```

---

### Task 1: 스캐폴드 + 설정 로딩

**Files:** Create `requirements.txt`, `.env.example`, `.gitignore`, `shorts/__init__.py`, `shorts/net.py`, `shorts/config.py`, `assets/{bgm,clips,images}/.gitkeep`. Test `tests/test_config.py`.

**Interfaces:** `Settings` dataclass, `Settings.from_env(env: Mapping[str,str]) -> Settings`, `load_settings(dotenv_path: str|None = ".env") -> Settings`, `net.enable_os_truststore() -> bool`.

- [ ] Step 1 테스트: 기본값이 무료/유료 차단(`allow_paid False`, `gemini_text_model == "gemini-3.5-flash"`, caps 50/100, `auto_publish == ()`, `youtube_privacy == "private"`); env 오버라이드(`ALLOW_PAID=true`, `GEMINI_DAILY_TEXT_CAP=7`, `AUTO_PUBLISH="youtube, instagram"` → 튜플).
- [ ] Step 2 실패 확인. Step 3 구현(Settings 필드: gemini_api_key, gemini_text_model, gemini_daily_text_cap, pollinations_daily_cap, tts_voice_animal="ko-KR-SunHiNeural", tts_voice_reporter="ko-KR-InJoonNeural", allow_paid, anthropic_api_key, claude_model="claude-opus-5", gemini_image_model="gemini-3.1-flash-image", kling_api_key, kling_base_url="https://api-singapore.klingai.com", elevenlabs_api_key, elevenlabs_voice_animal, elevenlabs_voice_reporter, font_path, output_dir="output", assets_dir="assets", use_os_truststore=True, auto_publish, youtube_privacy="private", youtube_client_secrets="client_secrets.json", youtube_token="token.json", ig_user_id, ig_access_token, ig_media_host="none", ig_copydir_path, ig_copydir_base_url). Step 4 통과. Step 5 커밋.

### Task 2: 비용 가드 + 사용량 원장

**Files:** `shorts/cost_guard.py`, `shorts/usage_ledger.py`; tests `test_cost_guard.py`, `test_usage_ledger.py`.

**Interfaces:** `PROVIDERS: dict[str, ProviderInfo(free, note)]`, `ensure_allowed(provider, allow_paid)`, `PaidProviderBlocked`, `QuotaExceeded`, `UsageLedger(path, today=None)` `.count(key)`, `.reserve(key, cap)`.

- [ ] 테스트: 무료 공급자는 항상 허용, 유료는 기본 차단·opt-in 시 허용, 미등록은 유료 취급; 원장은 일자별 카운트·영속·상한 초과 시 QuotaExceeded·날짜 바뀌면 0.
- [ ] 구현: PROVIDERS 표 = 무료 {gemini-text, pollinations, edge-tts, kenburns, local, placeholder, youtube, instagram, catbox}, 유료 {gemini-image, claude, kling, elevenlabs}. 원장은 JSON `{day: {key: n}}`.

### Task 3: ffmpeg 도구

**Files:** `shorts/ffmpeg_tools.py`; test `test_ffmpeg_tools.py`.

**Interfaces:** `ffmpeg_exe()`, `run_ffmpeg(args)`(`-hide_banner -y -nostdin` 접두, 실패 시 `FfmpegError` stderr 꼬리 포함), `probe_duration(path)`(`ffmpeg -i X -f null -` stderr의 마지막 `time=` 파싱), `probe_resolution(path)`(`Video:` 줄의 `WxH`), `make_silence(path, seconds)`(anullsrc 24kHz mono mp3).

- [ ] 테스트: 1.5초 무음 생성 후 길이 오차 <0.15; lavfi color 540x960 영상 해상도 파싱; 없는 파일 입력 시 FfmpegError.

### Task 4: 대본 모델 + 주제 + 대본 공급자

**Files:** `shorts/script_model.py`, `shorts/topics.py`, `shorts/script_gen.py`; tests `test_script_model.py`, `test_script_gen.py`.

**Interfaces:** `Line(speaker, text)`, `Script(topic, title, character, scene_prompt, lines, hashtags)` `.validate()`(3~6줄, title 20자, 줄 40자, speaker∉{reporter,animal}→animal, 해시태그 `#` 보정, 비면 기본 2개), `.to_dict()`, `from_dict(d, topic)`, `from_json(text, topic)`(```json 펜스/앞뒤 잡문 제거), `SCRIPT_JSON_SCHEMA`, `slugify(text, max_len=30)`(한글 유지), `random_topic()`, `ScriptProvider.generate(topic) -> Script`, `GeminiScriptProvider(settings, ledger)`(ensure_allowed + ledger.reserve → `generate_content(system_instruction, response_mime_type="application/json", response_json_schema=SCRIPT_JSON_SCHEMA, temperature=1.0)`), `ClaudeScriptProvider(settings)`(유료 게이트, `anthropic.Anthropic().messages.create(model=claude_model, max_tokens=2000, system=SYSTEM_PROMPT)`, refusal 처리), `PlaceholderScriptProvider()`(말순이 군밤 샘플 5줄), `SYSTEM_PROMPT`(한국어 규칙: 인터뷰 형식, 마지막 줄 반전, speaker enum, title 8~12자, scene_prompt 영어 photorealistic vertical, hashtags 4~6개 `#ai동물영상` 포함, JSON만), `build_user_prompt(topic)`.

### Task 5: 이미지 공급자

**Files:** `shorts/image_gen.py`; test `test_image_gen.py`.

**Interfaces:** `PORTRAIT=(1080,1920)`, `fit_portrait(img, size)`(cover crop), `ImageProvider.generate(prompt, out_path) -> Path`, `PollinationsImageProvider(settings, ledger, session=None)`(GET `https://image.pollinations.ai/prompt/{quote(prompt)}` params width/height/nologo/seed, 429/5xx 3회 백오프, content-type image 검증, reserve("pollinations")), `GeminiImageProvider(settings)`(유료 게이트, `response_modalities=["IMAGE"]`, `ImageConfig(aspect_ratio="9:16")`, `part.inline_data.data`), `LocalImageProvider(src)`, `PlaceholderImageProvider(font_path)`(그라데이션+프롬프트 텍스트).

- [ ] 테스트: fit_portrait 가로/세로 입력 모두 1080x1920; placeholder/local 결과 크기; FakeSession으로 pollinations URL 인코딩·params·원장 증가 확인.

### Task 6: 음성(TTS) + 자막 타이밍

**Files:** `shorts/tts.py`, `shorts/timing.py`; tests `test_timing.py`, `test_tts.py`.

**Interfaces:** `Cue(start, end, text, speaker)`, `build_cues(durations, texts, speakers, gap=0.25, lead_in=0.6)`, `total_duration(cues, tail=0.6)`, `Utterance(index, speaker, text, path, duration)`, `TTSProvider.synthesize(text, speaker, out_path)`, `EdgeTTSProvider(settings)`(animal: rate +8%, pitch +20Hz; `Communicate(...).save_sync`), `ElevenLabsTTSProvider(settings, session=None)`(유료 게이트, POST `/v1/text-to-speech/{voice}` `xi-api-key`, `eleven_multilingual_v2`), `SilentTTSProvider()`(0.5 + 0.12×글자수 초 무음), `synthesize_lines(script, provider, path_for) -> list[Utterance]`(파일 있으면 재사용, probe_duration로 길이).

- [ ] 테스트: [1.0, 2.0] → (0.6,1.6),(1.85,3.85), total 4.45; SilentTTS로 줄 수만큼 파일·길이>0.3.

### Task 7: 모션 영상 공급자

**Files:** `shorts/video_gen.py`; test `test_video_gen.py`.

**Interfaces:** `FPS=30`, `VideoProvider.generate(image_path, prompt, duration, out_path)`, `loop_fit_clip(src, duration, out_path)`(`-stream_loop -1`, scale increase+crop 1080x1920, fps 30), `KenBurnsVideoProvider()`(scale=2160:3840 → zoompan z 1.0→1.25 over d=frames, s=1080x1920), `LocalClipProvider(clip)`, `KlingVideoProvider(settings, session=None, sleep=time.sleep)`(유료 게이트; POST `{base}/image-to-video/kling-3.0` body `contents=[{type:prompt,text},{type:first_frame,url:<base64>}]`, `settings={resolution:"1080p", duration: 3..15, audio:"off", multi_shot:false}`, `options.external_task_id`; GET `{base}/tasks?external_task_ids=` 10초 폴링 최대 15분; `outputs[type=video].url` 다운로드 → loop_fit_clip).

- [ ] 테스트: kenburns 2.0초 → 1080x1920, 길이 오차 <0.2; local 640x360 1초 클립 → 2.5초로 루프·맞춤.

### Task 8: 오버레이 렌더 + 합성

**Files:** `shorts/overlay.py`, `shorts/compose.py`; tests `test_overlay.py`, `test_compose.py`.

**Interfaces:** `resolve_font(path)`(후보: 지정 → malgunbd → NotoSansKR-VF → malgun), `render_text_png(text, out_path, *, font_path, font_size, fill, stroke_fill, stroke_width, canvas, max_width)`(단어/글자 단위 줄바꿈, 중앙 정렬, RGBA), `render_title(title, out, font)`(1080x320, 형광초록 (120,255,60), 검정 외곽 10, 92pt), `render_subtitle(text, out, font)`(1080x300, 흰색, 검정 외곽 8, 68pt), `build_compose_command(*, video, title_png, subtitle_pngs, cues, utterances, bgm, total, out_path) -> list[str]`, `compose(**kwargs) -> Path`.

filter_complex 구성: `[0:v]trim=0:T,setpts,scale=1080:1920,format=yuv420p[v0]` → `[v0][1:v]overlay=(W-w)/2:130[v1]` → 자막 i: `overlay=(W-w)/2:H-h-260:enable='between(t,s,e)'` 체인 → `[vout]`; 오디오: 각 대사 `aresample=44100,aformat=fltp:stereo,adelay=ms|ms[ak]`, BGM 있으면 `-stream_loop -1` 입력 + `volume=0.12,atrim=0:T[abgm]`; `amix=inputs=n:normalize=0:dropout_transition=0,apad,atrim=0:T[aout]`(입력 1개면 amix 생략); 출력 `libx264 crf20 r30 yuv420p aac 160k -t T +faststart`.

- [ ] 테스트: 제목/자막 PNG가 RGBA·폭 1080·getbbox 비어있지 않음; 명령에 `between(t,0.6,1.6)`, `adelay=600|600`, `adelay=1850|1850`, `amix=inputs=2`, `-t 4.450`, 마지막 인자가 출력 경로.

### Task 9: 공급자 팩토리 + 파이프라인

**Files:** `shorts/providers.py`, `shorts/pipeline.py`; test `test_pipeline.py`.

**Interfaces:** `Providers(script, image, tts, video)`, `build_providers(settings, *, dry_run, video_provider, image_provider, script_provider, ledger, tts_provider=None)`(dry_run → Placeholder/Placeholder/Silent/KenBurns; 기본 gemini/pollinations/edge/kenburns; `assets/images`에 파일 있으면 local 이미지, `assets/clips`에 mp4 있으면 local 클립), `RunPaths(run_dir)`(script_json, scene_png, motion_mp4, title_png, final_mp4, meta_txt, manifest_json, line_mp3(i), subtitle_png(i)), `Manifest.load(path)`, `.mark(step, status, **extra)`, `.done(step)`, `.save()`, `make_run_dir(output_dir, title)`(`YYYYMMDD_HHMMSS_<slug>`), `find_bgm(assets_dir)`, `write_meta(script, path)`(제목 #Shorts, 캐릭터, 주제, 해시태그, 대사), `run_pipeline(settings, providers, topic, *, run_dir=None, publish=()) -> RunPaths`(단계: script → image → tts → motion → overlays → compose → meta → publish; `_step`이 done이면 건너뛰고 실패 시 manifest에 error/trace 기록 후 재raise).

- [ ] 테스트: dry-run 엔드투엔드로 final.mp4 1080x1920, 길이 5~25초, manifest compose done, meta에 해시태그/제목; 같은 run_dir로 재실행 시 final.mp4 mtime 불변.

### Task 10: 배포 (YouTube, 미디어 호스트, Instagram)

**Files:** `shorts/publish/__init__.py`, `youtube.py`, `media_host.py`, `instagram.py`; test `test_publish.py`.

**Interfaces:** `youtube.SCOPES=["https://www.googleapis.com/auth/youtube.upload"]`, `build_video_body(script, privacy)`(title에 `#Shorts` 보장, description에 해시태그, tags, categoryId "15", selfDeclaredMadeForKids False), `get_credentials(client_secrets, token_path)`(token.json 로드/refresh, 없으면 `InstalledAppFlow.run_local_server(port=0)` 후 저장), `upload_short(video_path, script, privacy, credentials) -> video_id`(`videos().insert(part="snippet,status", media_body=MediaFileUpload(chunksize=-1, resumable=True))` next_chunk 루프); `MediaHost.upload(path) -> url`, `CopyDirHost(dir, base_url)`, `CatboxHost(session=None)`(POST catbox `reqtype=fileupload`), `build_media_host(settings)`(none이면 안내 예외); `instagram.publish_reel(ig_user_id, token, video_url, caption, session=None, sleep=time.sleep)`(POST `/v25.0/{ig}/media` media_type=REELS, share_to_feed; GET status_code 10초 폴링 최대 10분, FINISHED → POST `/media_publish creation_id`); `publish_all(settings, script, video_path, targets, manifest) -> dict`(대상별 try/except, 결과 manifest["publish"]에 기록).

- [ ] 테스트: body 규칙; CopyDirHost 복사+URL; FakeSession으로 릴스 생성→폴링→게시 순서와 파라미터.

### Task 11: CLI + `--check` + README

**Files:** `main.py` 전체 교체, `README.md`; test `test_cli.py`.

**Interfaces:** `build_parser()`(--topic, --count, --publish, --dry-run, --allow-paid, --script-provider, --image-provider, --tts-provider, --video-provider, --resume, --check, --no-dotenv), `run_check(settings)`(ffmpeg 경로, 폰트, ALLOW_PAID, 오늘 사용량, Gemini 키/모델 목록 확인, 결제 미연결 안내, YouTube secrets/token, Instagram 설정, 공급자 표), `main(argv) -> int`(load_settings → truststore → check/resume/count 루프, 예외는 stderr에 한 줄 + rc 1).

- [ ] 테스트: 파서 기본값; `--dry-run --topic ... --no-dotenv`로 OUTPUT_DIR에 run 폴더와 final.mp4 생성.
- [ ] README(한국어): 설치, .env, Gemini 키 발급(결제 미연결 프로젝트), `--check`, 실행 예시, dry-run, 유료 옵션 경고, YouTube OAuth 절차, Instagram 절차(비즈니스 계정, `instagram_content_publish`, 공개 URL 호스트), assets 폴더, 출력 구조, 문제 해결(SSL/폰트/쿼터).
- [ ] 스펙 문서에 변경점(이미지 기본 pollinations, truststore, Kling Bearer API) 반영 후 커밋.

---

## Self-Review

- 스펙 커버리지: 비용 원칙(Task 2 + 각 공급자 생성자의 ensure_allowed/ledger.reserve), 파이프라인 1~7(Task 4~10), CLI(Task 11), .env 키(Task 1), 오류 처리/재개(Task 9), 테스트 전 태스크 — 모두 매핑됨.
- 스펙 대비 변경: 기본 이미지 공급자 pollinations(Gemini 이미지 유료 확인), truststore, Kling Bearer 방식. Task 11에서 스펙에 반영.
- 타입 일관성: `synthesize_lines(script, provider, path_for)`(Task 6↔9), `compose(**kwargs)` 키워드(Task 8↔9), `Manifest.done/mark/save`(Task 9↔10), `build_providers(..., tts_provider=)`(Task 9↔11) 일치.
