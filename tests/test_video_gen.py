from PIL import Image
from shorts.video_gen import KenBurnsVideoProvider, LocalClipProvider
from shorts.ffmpeg_tools import probe_duration, probe_resolution, run_ffmpeg


def test_kenburns_makes_portrait_clip_of_requested_length(tmp_path):
    img = tmp_path / "scene.png"
    Image.new("RGB", (1080, 1920), "green").save(img)
    out = KenBurnsVideoProvider().generate(img, "p", 2.0, tmp_path / "motion.mp4")
    assert probe_resolution(out) == (1080, 1920)
    assert abs(probe_duration(out) - 2.0) < 0.2


def test_local_clip_is_looped_and_fitted(tmp_path):
    src = tmp_path / "src.mp4"
    run_ffmpeg(["-f", "lavfi", "-i", "color=c=red:s=640x360:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)])
    out = LocalClipProvider(src).generate(tmp_path / "x.png", "p", 2.5, tmp_path / "motion.mp4")
    assert probe_resolution(out) == (1080, 1920)
    assert abs(probe_duration(out) - 2.5) < 0.2
