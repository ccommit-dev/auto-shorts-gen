from shorts.config import Settings


def test_defaults_are_free_and_paid_blocked():
    s = Settings.from_env({})
    assert s.allow_paid is False
    assert s.gemini_text_model == "gemini-3.5-flash"
    assert s.gemini_daily_text_cap == 50
    assert s.pollinations_daily_cap == 100
    assert s.auto_publish == ()
    assert s.youtube_privacy == "private"


def test_env_overrides_and_parsing():
    s = Settings.from_env({
        "ALLOW_PAID": "true", "GEMINI_API_KEY": "k", "GEMINI_DAILY_TEXT_CAP": "7",
        "AUTO_PUBLISH": "youtube, instagram", "OUTPUT_DIR": "out2",
    })
    assert s.allow_paid is True
    assert s.gemini_api_key == "k"
    assert s.gemini_daily_text_cap == 7
    assert s.auto_publish == ("youtube", "instagram")
    assert s.output_dir == "out2"
