"""제품 소개 영상용 한글 폰트(Pretendard, SIL Open Font License)를 assets/fonts 에 내려받는다.

무료 폰트이며 한 번만 받으면 된다. 받지 않아도 영상은 만들어지고, 맑은 고딕으로 렌더된다.
"""
from __future__ import annotations

import sys
from pathlib import Path

URLS = (
    "https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/variable/woff2/PretendardVariable.woff2",
    "https://fastly.jsdelivr.net/npm/pretendard@1.3.9/dist/web/variable/woff2/PretendardVariable.woff2",
)


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shorts.net import enable_os_truststore
    from shorts.promo.fonts import FILE_NAME
    enable_os_truststore()
    import requests

    out = Path("assets/fonts") / FILE_NAME
    if out.exists() and out.stat().st_size > 50_000:
        print(f"이미 있습니다: {out} ({out.stat().st_size:,} bytes)")
        return 0
    for url in URLS:
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 50_000:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(r.content)
                print(f"받았습니다: {out} ({len(r.content):,} bytes)")
                return 0
            print(f"  실패 HTTP {r.status_code}: {url}")
        except Exception as e:  # noqa: BLE001
            print(f"  실패 {type(e).__name__}: {url}")
    print("내려받지 못했습니다. 맑은 고딕으로 렌더됩니다.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
