from PIL import Image
from shorts.video_gen import KenBurnsVideoProvider, pingpong_clip, puppet_zoom_expr, loop_fit_clip
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


def test_pingpong_doubles_length_and_loops(tmp_path):
    src = tmp_path / "src.mp4"
    run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=320x576:rate=24:duration=1", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", str(src)])
    pp = pingpong_clip(src, tmp_path / "pp.mp4")
    assert abs(probe_duration(pp) - 2.0) < 0.15
    out = loop_fit_clip(pp, 5.0, tmp_path / "m.mp4")
    assert probe_resolution(out) == (1080, 1920) and abs(probe_duration(out) - 5.0) < 0.2
