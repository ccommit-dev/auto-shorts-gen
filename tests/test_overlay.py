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


def test_word_overlays_reveal_progressively(tmp_path):
    from shorts.overlay import render_subtitle_words
    f = resolve_font(None)
    words = ["못생긴", "언니", "오백원"]
    sizes = []
    for k in (1, 2, 3):
        p = render_subtitle_words(words, k, tmp_path / f"w{k}.png", f, punch=True)
        im = Image.open(p)
        assert im.mode == "RGBA" and im.width == 1080
        bbox = im.getbbox()
        sizes.append(bbox[2] - bbox[0])
    assert sizes[0] < sizes[1] < sizes[2]  # 어절이 늘수록 그려진 폭이 커진다


def test_title_popin_frames_scale_up(tmp_path):
    from shorts.overlay import render_title_popin
    t = render_title("장사 잘하는법", tmp_path / "t.png", resolve_font(None))
    frames = render_title_popin(t, tmp_path)
    widths = [Image.open(p).width for p in frames]
    assert len(frames) == 3 and widths[0] < widths[1] < widths[2] and widths[2] > 1080
