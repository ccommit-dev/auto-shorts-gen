from __future__ import annotations

import time

GRAPH = "https://graph.facebook.com/v25.0"


def publish_reel(ig_user_id: str, token: str, video_url: str, caption: str, session=None, sleep=time.sleep) -> str:
    """컨테이너 생성 → 처리 완료 폴링 → 게시. 게시된 미디어 ID 반환."""
    if session is None:
        import requests
        session = requests.Session()
    r = session.post(f"{GRAPH}/{ig_user_id}/media",
                     data={"media_type": "REELS", "video_url": video_url, "caption": caption[:2200],
                           "share_to_feed": "true", "access_token": token}, timeout=120)
    d = r.json()
    if "id" not in d:
        raise RuntimeError(f"릴스 컨테이너 생성 실패: {d}")
    container = d["id"]
    for _ in range(60):  # 최대 10분
        sleep(10)
        q = session.get(f"{GRAPH}/{container}", params={"fields": "status_code", "access_token": token},
                        timeout=60).json()
        status = q.get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"릴스 처리 실패: {q}")
    else:
        raise RuntimeError("릴스 처리가 시간 내에 끝나지 않았습니다")
    p = session.post(f"{GRAPH}/{ig_user_id}/media_publish",
                     data={"creation_id": container, "access_token": token}, timeout=120).json()
    if "id" not in p:
        raise RuntimeError(f"릴스 게시 실패: {p}")
    return p["id"]
