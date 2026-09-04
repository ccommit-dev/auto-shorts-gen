from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from ..config import Settings
from ..cost_guard import ensure_allowed


class MediaHost(Protocol):
    def upload(self, path: Path) -> str: ...


class CopyDirHost:
    """파일을 공개 웹 폴더(또는 동기화 폴더)로 복사하고 base_url + 파일명을 돌려준다."""

    def __init__(self, directory: Path, base_url: str):
        self.dir, self.base = Path(directory), base_url.rstrip("/") + "/"

    def upload(self, path: Path) -> str:
        self.dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, self.dir / Path(path).name)
        return self.base + Path(path).name


class CatboxHost:
    """catbox.moe 무료 익명 호스팅 (opt-in)."""
    name = "catbox"

    def __init__(self, session=None):
        if session is None:
            import requests
            session = requests.Session()
        self.session = session

    def upload(self, path: Path) -> str:
        with open(path, "rb") as f:
            r = self.session.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"},
                                  files={"fileToUpload": (Path(path).name, f, "video/mp4")}, timeout=600)
        if r.status_code != 200 or not r.text.startswith("https://"):
            raise RuntimeError(f"catbox 업로드 실패: HTTP {r.status_code} {r.text[:200]}")
        return r.text.strip()


def build_media_host(settings: Settings) -> MediaHost:
    if settings.ig_media_host == "catbox":
        ensure_allowed("catbox", settings.allow_paid)
        return CatboxHost()
    if settings.ig_media_host == "copydir":
        if not (settings.ig_copydir_path and settings.ig_copydir_base_url):
            raise RuntimeError("IG_COPYDIR_PATH 와 IG_COPYDIR_BASE_URL 이 필요합니다")
        return CopyDirHost(Path(settings.ig_copydir_path), settings.ig_copydir_base_url)
    raise RuntimeError("인스타 릴스는 공개 URL이 필요합니다. IG_MEDIA_HOST=catbox 또는 copydir 를 설정하세요.")
