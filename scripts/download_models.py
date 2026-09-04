r"""로컬 무료 AI 영상용 LTX-Video 모델을 미리 내려받는다 (약 24GB, 최초 1회).

사용: .venv\Scripts\python scripts\download_models.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")  # 사내망 SSL 검사 환경에서는 파이썬 SSL(truststore) 경로만 동작

from shorts.config import load_settings  # noqa: E402
from shorts.net import enable_os_truststore  # noqa: E402


def main() -> int:
    s = load_settings(".env" if Path(".env").exists() else None)
    if s.use_os_truststore:
        enable_os_truststore()
    from huggingface_hub import snapshot_download
    print(f"downloading {s.ltx_model} ...", flush=True)
    local_dir = Path(s.models_dir) / s.ltx_model.split("/")[-1]
    local_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_download(s.ltx_model, local_dir=str(local_dir),
                             ignore_patterns=["media/*", "*.md", "*.png", "*.mp4"], max_workers=4)
    print(f"done: {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
