from PIL import Image
from shorts.video_gen import (KenBurnsVideoProvider, LocalClipProvider, assemble_by_speaker, loop_fit_clip,
                              puppet_zoom_expr, speaker_segments)
from shorts.timing import Cue
from shorts.ffmpeg_tools import probe_duration, probe_resolution, run_ffmpeg


def test_puppet_expr_gates_on_animal_cues_only():
    cues = [Cue(0.5, 1.5, "q", "reporter"), Cue(1.8, 3.0, "a", "animal")]
    e = puppet_zoom_expr(cues, frames=120)
    assert "between(on/30,1.8,3)" in e and "between(on/30,0.5,1.5)" not in e
    assert puppet_zoom_expr([Cue(0, 1, "q", "reporter")], 30) == "1.0+0.2*on/30"


def test_kenburns_with_cues_renders(tmp_path):
    img = tmp_path / "scene.png"
    Image.new("RGB", (1080, 1920), "green").save(img)
    cues = [Cue(0.3, 0.8, "q", "reporter"), Cue(1.0, 1.8, "a", "animal")]
    out = KenBurnsVideoProvider().generate(img, "p", 2.0, tmp_path / "m.mp4", cues=cues)
    assert probe_resolution(out) == (1080, 1920) and abs(probe_duration(out) - 2.0) < 0.2


def test_speaker_segments_split_talk_and_listen():
    cues = [Cue(0.6, 1.6, "q", "reporter"), Cue(1.85, 3.0, "a", "animal"), Cue(3.25, 4.0, "b", "animal")]
    segs = speaker_segments(cues, total=4.6)
    assert segs == [(0.0, 1.85, "listen"), (1.85, 3.0, "talk"), (3.0, 3.25, "listen"),
                    (3.25, 4.0, "talk"), (4.0, 4.6, "listen")]
    assert speaker_segments([], 2.0) == [(0.0, 2.0, "listen")]


def _clip(path, color, seconds):
    run_ffmpeg(["-f", "lavfi", "-i", f"color=c={color}:s=320x576:r=24:d={seconds}", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", str(path)])
    return path


def test_assemble_by_speaker_cuts_between_clips(tmp_path):
    talk = _clip(tmp_path / "talk.mp4", "red", 2)
    listen = _clip(tmp_path / "listen.mp4", "blue", 2)
    cues = [Cue(0.5, 1.0, "q", "reporter"), Cue(1.2, 4.5, "a", "animal")]  # talk 구간이 클립(2초)보다 길다
    out = assemble_by_speaker(talk, listen, cues, 5.0, tmp_path / "m.mp4")
    assert probe_resolution(out) == (1080, 1920) and abs(probe_duration(out) - 5.0) < 0.2
    # 0.6초 지점은 listen(파랑), 2.0초 지점은 talk(빨강)
    for t, expect in ((0.6, "blue"), (2.0, "red")):
        png = tmp_path / f"f{t}.png"
        run_ffmpeg(["-ss", str(t), "-i", str(out), "-frames:v", "1", str(png)])
        r, g, b = Image.open(png).convert("RGB").getpixel((540, 960))
        assert (b > r) if expect == "blue" else (r > b)


def test_local_clip_provider_picks_listen_by_name(tmp_path):
    talk = _clip(tmp_path / "dog_talk.mp4", "red", 1)
    listen = _clip(tmp_path / "dog_listen.mp4", "blue", 1)
    p = LocalClipProvider([talk, listen])
    assert p.talk == talk and p.listen == listen
    single = LocalClipProvider([talk])
    assert single.talk == talk and single.listen == talk
    out = p.generate(tmp_path / "x.png", "p", 2.5, tmp_path / "m.mp4", cues=[Cue(0.5, 1.5, "a", "animal")])
    assert abs(probe_duration(out) - 2.5) < 0.2


def test_loop_fit_clip_extends_forward(tmp_path):
    src = _clip(tmp_path / "src.mp4", "red", 1)
    out = loop_fit_clip(src, 3.0, tmp_path / "m.mp4")
    assert probe_resolution(out) == (1080, 1920) and abs(probe_duration(out) - 3.0) < 0.2
