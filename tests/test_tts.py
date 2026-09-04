import json
from shorts.tts import SilentTTSProvider, synthesize_lines, load_words, words_path
from shorts.script_gen import PlaceholderScriptProvider


def test_synthesize_lines_measures_durations_and_even_words(tmp_path):
    script = PlaceholderScriptProvider().generate("x")
    utts = synthesize_lines(script, SilentTTSProvider(), path_for=lambda i: tmp_path / f"line_{i:02d}.mp3")
    assert len(utts) == len(script.lines)
    assert all(u.path.exists() and u.duration > 0.3 for u in utts)
    assert utts[0].speaker == "reporter"
    assert [w[2] for w in utts[1].words] == ["예쁜", "언니", "천원"]


def test_load_words_parses_edge_tts_metadata(tmp_path):
    mp3 = tmp_path / "l.mp3"
    mp3.write_bytes(b"")
    rows = [{"type": "WordBoundary", "offset": 962910, "duration": 5092500, "text": "못생긴"},
            {"type": "WordBoundary", "offset": 6171250, "duration": 3240830, "text": "언니"},
            {"type": "SentenceBoundary", "offset": 0, "duration": 0, "text": "x"}]
    words_path(mp3).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), "utf-8")
    ws = load_words(mp3, "못생긴 언니", 1.5)
    assert ws == [(0.096, 0.606, "못생긴"), (0.617, 0.941, "언니")]
