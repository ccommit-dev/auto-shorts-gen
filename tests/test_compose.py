from pathlib import Path
from shorts.compose import build_compose_command, Overlay
from shorts.timing import Cue
from shorts.tts import Utterance


def _base(**kw):
    cues = [Cue(0.6, 1.6, "a", "reporter"), Cue(1.85, 3.85, "b", "animal", punch=True)]
    utts = [Utterance(0, "reporter", "a", Path("l0.mp3"), 1.0), Utterance(1, "animal", "b", Path("l1.mp3"), 2.0)]
    args = dict(video=Path("m.mp4"), title_png=Path("t.png"),
                overlays=[Overlay(Path("s0.png"), 0.6, 1.6), Overlay(Path("s1.png"), 1.85, 2.5),
                          Overlay(Path("s2.png"), 2.5, 3.85)],
                cues=cues, utterances=utts, bgm=None, total=4.45, out_path=Path("final.mp4"))
    args.update(kw)
    return build_compose_command(**args)


def test_command_has_overlays_enabled_by_window_and_audio_delays():
    cmd = _base()
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "between(t,0.6,1.6)" in fc and "between(t,1.85,2.5)" in fc and "between(t,2.5,3.85)" in fc
    assert "adelay=600|600" in fc and "adelay=1850|1850" in fc
    assert "amix=inputs=2" in fc and cmd[cmd.index("-t") + 1] == "4.450"
    assert cmd[-1] == "final.mp4" and "[vz]" not in fc


def test_punch_zoom_and_bgm():
    cmd = _base(punch=(1.85, 4.45), bgm=Path("bgm.mp3"))
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "scale=1166:2074,crop=1080:1920[vz]" in fc and "between(t,1.85,4.45)" in fc
    assert "-stream_loop" in cmd and "volume=0.12" in fc and "amix=inputs=3" in fc


def test_sfx_reverb_loudnorm_freeze_and_title_popin():
    from shorts.compose import Sfx
    cmd = _base(sfx=[Sfx(Path("pop.wav"), 1.85), Sfx(Path("ding.wav"), 3.0)],
                title_frames=[Overlay(Path("t0.png"), 0.0, 0.1), Overlay(Path("t1.png"), 0.1, 0.2)],
                end_freeze=0.5)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "aecho=" in fc and "loudnorm=" in fc
    assert "adelay=1850|1850[sfx0]" in fc and "adelay=3000|3000[sfx1]" in fc
    assert "tpad=stop_mode=clone:stop_duration=0.500" in fc and "trim=0:3.950" in fc
    assert "between(t,0,0.1)" in fc and "gte(t,0.2)" in fc
    assert "amix=inputs=4" in fc
