from shorts.config import Settings
from shorts.providers import build_providers
from shorts.usage_ledger import UsageLedger
from shorts.video_gen import KenBurnsVideoProvider, LocalClipProvider
from shorts import providers as prov_mod


def test_auto_video_prefers_local_clip_then_gpu_then_kenburns(tmp_path, monkeypatch):
    s = Settings(gemini_api_key="k", assets_dir=str(tmp_path / "assets"))
    led = UsageLedger(tmp_path / "u.json")
    monkeypatch.setattr(prov_mod, "ltx_available", lambda: False)
    p = build_providers(s, dry_run=False, video_provider=None, image_provider=None, script_provider=None, ledger=led)
    assert isinstance(p.video, KenBurnsVideoProvider)
    (tmp_path / "assets" / "clips").mkdir(parents=True)
    (tmp_path / "assets" / "clips" / "a.mp4").write_bytes(b"x")
    (tmp_path / "assets" / "clips" / "a_listen.mp4").write_bytes(b"x")
    p = build_providers(s, dry_run=False, video_provider=None, image_provider=None, script_provider=None, ledger=led)
    assert isinstance(p.video, LocalClipProvider)
    assert p.video.listen.name == "a_listen.mp4" and p.video.talk.name == "a.mp4"
