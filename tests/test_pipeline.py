from shorts.config import Settings
from shorts.pipeline import run_pipeline, Manifest
from shorts.providers import build_providers
from shorts.usage_ledger import UsageLedger
from shorts.ffmpeg_tools import probe_duration, probe_resolution


def _providers(tmp_path, s):
    return build_providers(s, dry_run=True, video_provider=None, image_provider=None, script_provider=None,
                           ledger=UsageLedger(tmp_path / "u.json"))


def test_dry_run_end_to_end(tmp_path):
    s = Settings(output_dir=str(tmp_path / "out"), assets_dir=str(tmp_path / "assets"))
    paths = run_pipeline(s, _providers(tmp_path, s), "강아지 군밤장사")
    assert paths.final_mp4.exists() and paths.meta_txt.exists() and paths.script_json.exists()
    assert probe_resolution(paths.final_mp4) == (1080, 1920)
    assert 5 < probe_duration(paths.final_mp4) < 25
    m = Manifest.load(paths.manifest_json)
    assert m.data["steps"]["compose"]["status"] == "done"
    meta = paths.meta_txt.read_text("utf-8")
    assert "#ai동물영상" in meta and "장사 잘하는법" in meta


def test_resume_skips_finished_steps(tmp_path):
    s = Settings(output_dir=str(tmp_path / "out"), assets_dir=str(tmp_path / "assets"))
    prov = _providers(tmp_path, s)
    paths = run_pipeline(s, prov, "x")
    mtime = paths.final_mp4.stat().st_mtime
    paths2 = run_pipeline(s, prov, "x", run_dir=paths.run_dir)
    assert paths2.final_mp4.stat().st_mtime == mtime
