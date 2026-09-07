from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FALLBACK_FONTS = ["C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/NotoSansKR-VF.ttf", "C:/Windows/Fonts/malgun.ttf"]


def resolve_font(path: str | None) -> str | None:
    for cand in ([path] if path else []) + FALLBACK_FONTS:
        if cand and Path(cand).exists():
            return cand
    return None


def _font(path: str | None, size: int):
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    out = []  # 붙여쓴 긴 한국어는 글자 단위로 분할
    for ln in lines:
        while draw.textlength(ln, font=font) > max_width and len(ln) > 1:
            cut = max(1, int(len(ln) * max_width / draw.textlength(ln, font=font)))
            out.append(ln[:cut])
            ln = ln[cut:]
        out.append(ln)
    return out


def render_text_png(text: str, out_path: Path, *, font_path: str | None, font_size: int, fill, stroke_fill,
                    stroke_width: int, canvas: tuple[int, int], max_width: int) -> Path:
    img = Image.new("RGBA", canvas, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font(font_path, font_size)
    lines = _wrap(d, text, font, max_width)
    line_h = font_size + 12
    y = (canvas[1] - line_h * len(lines)) // 2
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((canvas[0] - w) / 2, y), ln, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
        y += line_h
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def render_title(title: str, out_path: Path, font_path: str | None) -> Path:
    return render_text_png(title, out_path, font_path=font_path, font_size=92, fill=(120, 255, 60, 255),
                           stroke_fill=(0, 0, 0, 255), stroke_width=10, canvas=(1080, 320), max_width=960)


def render_subtitle(text: str, out_path: Path, font_path: str | None) -> Path:
    return render_text_png(text, out_path, font_path=font_path, font_size=68, fill=(255, 255, 255, 255),
                           stroke_fill=(0, 0, 0, 255), stroke_width=8, canvas=(1080, 300), max_width=960)


PUNCH_FILL = (255, 222, 0, 255)


def render_subtitle_words(words: list[str], visible: int, out_path: Path, font_path: str | None,
                          punch: bool = False) -> Path:
    """전체 줄의 배치는 고정한 채 앞에서 visible 개 어절만 그린다 (단어가 하나씩 튀어나오는 자막).

    punch=True 면 펀치라인 스타일(노란색, 더 큰 글씨).
    """
    font_size = 78 if punch else 68
    fill = PUNCH_FILL if punch else (255, 255, 255, 255)
    canvas, max_width, stroke = (1080, 300), 960, 8
    img = Image.new("RGBA", canvas, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font(font_path, font_size)
    # 어절 단위로 줄바꿈: 폭을 넘기면 다음 줄
    lines: list[list[str]] = [[]]
    for w in words:
        trial = " ".join(lines[-1] + [w])
        if lines[-1] and d.textlength(trial, font=font) > max_width:
            lines.append([w])
        else:
            lines[-1].append(w)
    line_h = font_size + 12
    y = (canvas[1] - line_h * len(lines)) // 2
    shown = 0
    space = d.textlength(" ", font=font)
    for ln in lines:
        x = (canvas[0] - d.textlength(" ".join(ln), font=font)) / 2
        for w in ln:
            if shown < visible:
                d.text((x, y), w, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
            shown += 1
            x += d.textlength(w, font=font) + space
        y += line_h
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def render_title_popin(title_png: Path, out_dir: Path, scales=(0.55, 0.85, 1.1)) -> list[Path]:
    """제목 PNG 를 여러 배율로 저장해 팝인 애니메이션 프레임을 만든다 (작게 → 살짝 크게 → 원래 크기)."""
    base = Image.open(title_png).convert("RGBA")
    out = []
    for i, sc in enumerate(scales):
        p = Path(out_dir) / f"title_pop_{i:02d}.png"
        base.resize((max(1, int(base.width * sc)), max(1, int(base.height * sc))), Image.LANCZOS).save(p, "PNG")
        out.append(p)
    return out
