from PIL import Image
from shorts.overlay import render_title, render_subtitle, resolve_font


def test_title_and_subtitle_pngs_are_transparent_full_width(tmp_path):
    f = resolve_font(None)
    t = render_title("장사 잘하는법", tmp_path / "t.png", f)
    s = render_subtitle("예쁜 언니 천원 못생긴 언니 오백원 그리고 아주 긴 문장입니다", tmp_path / "s.png", f)
    for p in (t, s):
        im = Image.open(p)
        assert im.mode == "RGBA" and im.width == 1080
        assert im.getbbox() is not None


def test_resolve_font_prefers_existing_windows_font():
    f = resolve_font("C:/definitely/missing.ttf")
    assert f is None or f.lower().endswith(".ttf")
