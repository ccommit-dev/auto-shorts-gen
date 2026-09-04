from shorts.tts import SilentTTSProvider, synthesize_lines
from shorts.script_gen import PlaceholderScriptProvider


def test_synthesize_lines_measures_durations(tmp_path):
    script = PlaceholderScriptProvider().generate("x")
    utts = synthesize_lines(script, SilentTTSProvider(), path_for=lambda i: tmp_path / f"line_{i:02d}.mp3")
    assert len(utts) == len(script.lines)
    assert all(u.path.exists() and u.duration > 0.3 for u in utts)
    assert utts[0].speaker == "reporter"
