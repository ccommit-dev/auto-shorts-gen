"""본문 폰트(Pretendard, SIL OFL)를 브라우저에 끼워 넣는다.

파일이 없으면 조용히 건너뛰고 시스템 폰트(맑은 고딕)로 렌더한다.
`scripts/download_fonts.py` 로 받아 두면 자동으로 쓰인다.
"""
from __future__ import annotations

import base64
from pathlib import Path

FILE_NAME = "PretendardVariable.woff2"
FAMILY = "Pretendard Variable"


def find_font(assets_dir: str | Path) -> Path | None:
    p = Path(assets_dir) / "fonts" / FILE_NAME
    return p if p.exists() and p.stat().st_size > 50_000 else None


def font_css(path: str | Path) -> str:
    """woff2 를 data URI 로 심은 @font-face. file:// 페이지에서도 확실히 로드된다."""
    b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return (f"@font-face{{font-family:'{FAMILY}';font-weight:45 920;font-style:normal;"
            f"font-display:block;src:url(data:font/woff2;base64,{b64}) format('woff2-variations');}}")
