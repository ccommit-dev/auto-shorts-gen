import pytest
from shorts.usage_ledger import UsageLedger, QuotaExceeded


def test_reserve_counts_per_day_and_persists(tmp_path):
    p = tmp_path / "usage.json"
    led = UsageLedger(p, today=lambda: "2026-09-04")
    led.reserve("gemini-text", cap=2)
    led.reserve("gemini-text", cap=2)
    assert led.count("gemini-text") == 2
    with pytest.raises(QuotaExceeded):
        led.reserve("gemini-text", cap=2)
    assert UsageLedger(p, today=lambda: "2026-09-04").count("gemini-text") == 2


def test_new_day_resets(tmp_path):
    p = tmp_path / "usage.json"
    UsageLedger(p, today=lambda: "2026-09-04").reserve("x", cap=1)
    assert UsageLedger(p, today=lambda: "2026-09-05").count("x") == 0
