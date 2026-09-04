from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Callable


class QuotaExceeded(RuntimeError):
    pass


def _utc_today() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


class UsageLedger:
    """무료 API 일일 호출 수를 로컬 JSON에 기록해 상한을 강제한다."""

    def __init__(self, path: Path, today: Callable[[], str] | None = None):
        self.path = Path(path)
        self._today = today or _utc_today

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text("utf-8"))
        except json.JSONDecodeError:
            return {}

    def count(self, key: str) -> int:
        return int(self._load().get(self._today(), {}).get(key, 0))

    def reserve(self, key: str, cap: int) -> None:
        data = self._load()
        day = data.setdefault(self._today(), {})
        n = int(day.get(key, 0))
        if n >= cap:
            raise QuotaExceeded(
                f"오늘 '{key}' 호출 {n}회로 일일 상한({cap})에 도달했습니다. "
                f"내일 다시 시도하거나 상한을 올리세요.")
        day[key] = n + 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
