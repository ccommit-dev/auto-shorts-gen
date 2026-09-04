from main import build_parser, main


def test_parser_defaults():
    a = build_parser().parse_args([])
    assert a.count == 1 and a.dry_run is False and a.publish == "" and a.topic is None


def test_dry_run_creates_output(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("ASSETS_DIR", str(tmp_path / "assets"))
    rc = main(["--dry-run", "--topic", "고양이 편의점 알바", "--no-dotenv"])
    assert rc == 0
    runs = [p for p in (tmp_path / "out").iterdir() if p.is_dir()]
    assert len(runs) == 1 and (runs[0] / "final.mp4").exists()


def test_paid_provider_is_blocked_without_opt_in(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    monkeypatch.setenv("KLING_API_KEY", "dummy")
    rc = main(["--topic", "x", "--video-provider", "kling", "--no-dotenv"])
    assert rc == 1
