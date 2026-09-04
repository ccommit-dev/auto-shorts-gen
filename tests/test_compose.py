from pathlib import Path
from shorts.compose import build_compose_command
from shorts.timing import Cue
from shorts.tts import Utterance


def test_command_has_overlays_enabled_by_cue_and_audio_delays():
    cues = [Cue(0.6, 1.6, "a", "reporter"), Cue(1.85, 3.85, "b", "animal")]
    utts = [Utterance(0, "reporter", "a", Path("l0.mp3"), 1.0), Utterance(1, "animal", "b", Path("l1.mp3"), 2.0)]
    cmd = build_compose_command(video=Path("m.mp4"), title_png=Path("t.png"),
                                subtitle_pngs=[Path("s0.png"), Path("s1.png")],
                                cues=cues, utterances=utts, bgm=None, total=4.45, out_path=Path("final.mp4"))
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "between(t,0.6,1.6)" in fc and "between(t,1.85,3.85)" in fc
    assert "adelay=600|600" in fc and "adelay=1850|1850" in fc
    assert "amix=inputs=2" in fc
    assert cmd[cmd.index("-t") + 1] == "4.450"
    assert cmd[-1] == "final.mp4"


def test_bgm_adds_looped_input_and_third_mix_channel():
    cues = [Cue(0.6, 1.6, "a", "reporter")]
    utts = [Utterance(0, "reporter", "a", Path("l0.mp3"), 1.0)]
    cmd = build_compose_command(video=Path("m.mp4"), title_png=Path("t.png"), subtitle_pngs=[Path("s0.png")],
                                cues=cues, utterances=utts, bgm=Path("bgm.mp3"), total=2.2, out_path=Path("f.mp4"))
    assert "-stream_loop" in cmd
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "volume=0.12" in fc and "amix=inputs=2" in fc
