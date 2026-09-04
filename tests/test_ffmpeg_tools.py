import pytest
from shorts.ffmpeg_tools import ffmpeg_exe, make_silence, probe_duration, run_ffmpeg, FfmpegError, probe_resolution


def test_ffmpeg_available():
    assert "ffmpeg" in ffmpeg_exe().lower()


def test_silence_duration(tmp_path):
    p = make_silence(tmp_path / "s.mp3", 1.5)
    assert p.exists()
    assert abs(probe_duration(p) - 1.5) < 0.15


def test_resolution_of_generated_video(tmp_path):
    out = tmp_path / "c.mp4"
    run_ffmpeg(["-f", "lavfi", "-i", "color=c=black:s=540x960:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)])
    assert probe_resolution(out) == (540, 960)


def test_run_ffmpeg_raises_on_error(tmp_path):
    with pytest.raises(FfmpegError):
        run_ffmpeg(["-i", str(tmp_path / "missing.mp4"), str(tmp_path / "o.mp4")])
