from __future__ import annotations

from pathlib import Path

from ..config import Settings
from ..cost_guard import ensure_allowed
from ..script_model import Script


def publish_all(settings: Settings, script: Script, video_path: Path, targets, manifest) -> dict:
    """대상별로 배포하고 결과를 manifest['publish']에 기록. 한 대상이 실패해도 나머지는 진행."""
    results: dict = {}
    for target in targets:
        try:
            if target == "youtube":
                from .youtube import get_credentials, upload_short
                ensure_allowed("youtube", settings.allow_paid)
                creds = get_credentials(settings.youtube_client_secrets, settings.youtube_token)
                vid = upload_short(video_path, script, settings.youtube_privacy, creds)
                results[target] = {"status": "done", "id": vid, "url": f"https://youtube.com/shorts/{vid}"}
            elif target == "instagram":
                from .instagram import publish_reel
                from .media_host import build_media_host
                ensure_allowed("instagram", settings.allow_paid)
                if not (settings.ig_user_id and settings.ig_access_token):
                    raise RuntimeError("IG_USER_ID 와 IG_ACCESS_TOKEN 이 필요합니다")
                url = build_media_host(settings).upload(video_path)
                caption = f"{script.title}\n\n{' '.join(script.hashtags)}"
                mid = publish_reel(settings.ig_user_id, settings.ig_access_token, url, caption)
                results[target] = {"status": "done", "id": mid, "video_url": url}
            else:
                raise RuntimeError(f"알 수 없는 배포 대상: {target}")
            print(f"  [publish] {target}: {results[target]}")
        except Exception as e:
            results[target] = {"status": "failed", "error": f"{type(e).__name__}: {e}"}
            print(f"  [publish] {target} 실패: {e}")
        manifest.data["publish"][target] = results[target]
        manifest.save()
    return results
