from __future__ import annotations

from pathlib import Path

from ..script_model import Script

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def build_video_body(script: Script, privacy: str, shorts: bool = True) -> dict:
    """shorts=False 는 가로 제품 소개 영상용: #Shorts 를 붙이지 않고 카테고리를 과학기술로 둔다."""
    tag = " #Shorts" if shorts else ""
    title = script.title if (not shorts or "#shorts" in script.title.lower()) else f"{script.title}{tag}"
    desc = f"{script.character}\n{script.topic}\n\n{' '.join(script.hashtags)}{tag}".strip()
    return {"snippet": {"title": title[:100], "description": desc[:5000],
                        "tags": [h.lstrip("#") for h in script.hashtags][:20],
                        "categoryId": "15" if shorts else "28"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}


def get_credentials(client_secrets: str, token_path: str):
    """token.json 이 있으면 재사용/갱신, 없으면 브라우저 OAuth 승인 후 저장."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    creds = Credentials.from_authorized_user_file(token_path, SCOPES) if Path(token_path).exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not Path(client_secrets).exists():
            raise RuntimeError(f"{client_secrets} 가 없습니다. Google Cloud Console에서 "
                               "OAuth 데스크톱 클라이언트를 만들어 내려받으세요.")
        creds = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES).run_local_server(port=0)
        Path(token_path).write_text(creds.to_json(), "utf-8")
    return creds


def upload_short(video_path: Path, script: Script, privacy: str, credentials, shorts: bool = True) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    yt = build("youtube", "v3", credentials=credentials)
    req = yt.videos().insert(part="snippet,status", body=build_video_body(script, privacy, shorts),
                             media_body=MediaFileUpload(str(video_path), chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]
