import pytest
from shorts.cost_guard import ensure_allowed, PaidProviderBlocked, PROVIDERS


def test_free_provider_always_allowed():
    ensure_allowed("pollinations", allow_paid=False)
    ensure_allowed("edge-tts", allow_paid=False)


def test_paid_provider_blocked_by_default():
    with pytest.raises(PaidProviderBlocked):
        ensure_allowed("kling", allow_paid=False)


def test_paid_provider_allowed_when_opted_in():
    ensure_allowed("kling", allow_paid=True)


def test_unknown_provider_is_treated_as_paid():
    with pytest.raises(PaidProviderBlocked):
        ensure_allowed("mystery", allow_paid=False)


def test_table_marks_expected_free_and_paid():
    assert PROVIDERS["gemini-text"].free and PROVIDERS["youtube"].free
    assert not PROVIDERS["gemini-image"].free and not PROVIDERS["claude"].free
