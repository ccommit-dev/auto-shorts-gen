from shorts.audio_assets import ensure_audio_assets, make_ding, make_pop
from shorts.ffmpeg_tools import probe_duration
from shorts.tts import voice_variation


def test_audio_assets_are_created_once_and_user_bgm_wins(tmp_path):
    a = ensure_audio_assets(tmp_path)
    assert a["ding"].exists() and a["pop"].exists() and a["bgm"].name == "default_bgm.mp3"
    assert abs(probe_duration(a["ding"]) - 0.85) < 0.1
    assert probe_duration(a["bgm"]) > 20
    mtime = a["bgm"].stat().st_mtime
    (tmp_path / "bgm" / "mine.mp3").write_bytes(a["bgm"].read_bytes())
    b = ensure_audio_assets(tmp_path)
    assert b["bgm"].name == "mine.mp3" and a["bgm"].stat().st_mtime == mtime


def test_voice_variation_cycles_per_line():
    assert voice_variation("animal", 0) != voice_variation("animal", 1)
    assert voice_variation("animal", 0) == voice_variation("animal", 4)
    assert voice_variation("reporter", 0) == ("+0%", "+0Hz")
