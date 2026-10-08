"""브라우저로 한 프레임씩 그려 ffmpeg 으로 묶는다.

CSS 애니메이션 대신 JS `seek(t)` 로 시점을 직접 지정하므로, 느린 PC 에서도 결과가 같다.
브라우저는 이미 설치된 Edge/Chrome 을 쓰고, 없으면 Playwright 동봉 Chromium 을 쓴다.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from ..ffmpeg_tools import FfmpegError, ffmpeg_exe
from .fonts import font_css

TEMPLATE_DIR = Path(__file__).parent / "template"
CHANNELS = ("msedge", "chrome", "chromium")


class BrowserUnavailable(RuntimeError):
    pass


def page_url() -> str:
    return (TEMPLATE_DIR / "index.html").resolve().as_uri()


def _launch(pw, channel: str):
    """요청한 채널부터 차례로 시도한다. 'chromium' 은 Playwright 가 내려받은 브라우저."""
    order = [channel] + [c for c in CHANNELS if c != channel]
    errors = []
    for ch in order:
        try:
            return pw.chromium.launch() if ch == "chromium" else pw.chromium.launch(channel=ch)
        except Exception as e:  # noqa: BLE001 - 다음 채널로 넘어가기 위해 모두 받는다
            errors.append(f"{ch}: {type(e).__name__}")
    raise BrowserUnavailable(
        "브라우저를 찾지 못했습니다 (" + ", ".join(errors) + "). "
        "Edge/Chrome 을 설치하거나 '.venv\\Scripts\\python -m playwright install chromium' 을 실행하세요.")


def _open_page(pw, timeline: dict, width: int, height: int, channel: str, font_file: Path | None = None):
    browser = _launch(pw, channel)
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
    page.goto(page_url())
    page.wait_for_function("window.promoReady === true", timeout=20000)
    if font_file is not None:
        page.add_style_tag(content=font_css(font_file))
        page.evaluate("() => document.fonts.ready")
    page.evaluate("spec => window.build(spec)", timeline)
    page.wait_for_timeout(250)  # 웹폰트/레이아웃 안정화
    return browser, page


def render_poster(timeline: dict, out_png: Path, at: float, *, width: int = 1920, height: int = 1080,
                  channel: str = "msedge", font_file: Path | None = None) -> Path:
    from playwright.sync_api import sync_playwright
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser, page = _open_page(pw, timeline, width, height, channel, font_file)
        page.evaluate("t => window.seek(t)", float(at))
        page.screenshot(path=str(out_png), animations="disabled")
        browser.close()
    return out_png


def render_silent_video(timeline: dict, out_mp4: Path, *, fps: int = 30, width: int = 1920, height: int = 1080,
                        channel: str = "msedge", quality: int = 95, crf: int = 19,
                        font_file: Path | None = None,
                        on_progress: Callable[[int, int], None] | None = None) -> Path:
    """timeline 대로 전 프레임을 캡처해 무음 mp4 를 만든다 (프레임을 디스크에 남기지 않는다)."""
    from playwright.sync_api import sync_playwright

    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(round(float(timeline["total"]) * fps)))
    cmd = [ffmpeg_exe(), "-hide_banner", "-y", "-nostdin", "-f", "image2pipe", "-framerate", str(fps),
           "-i", "-", "-vf", "scale=in_range=full:out_range=tv,format=yuv420p",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709",
           "-color_trc", "bt709", "-movflags", "+faststart", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        with sync_playwright() as pw:
            browser, page = _open_page(pw, timeline, width, height, channel, font_file)
            for n in range(frames):
                page.evaluate("t => window.seek(t)", n / fps)
                proc.stdin.write(page.screenshot(type="jpeg", quality=quality, animations="disabled"))
                if on_progress and n % fps == 0:
                    on_progress(n, frames)
            browser.close()
    except BrokenPipeError as e:
        raise FfmpegError(f"ffmpeg 파이프가 끊겼습니다: {e}") from e
    finally:
        try:
            proc.stdin.close()
        except (OSError, ValueError):
            pass
        err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        rc = proc.wait()
    if rc != 0:
        raise FfmpegError("프레임 인코딩 실패:\n" + "\n".join(err.strip().splitlines()[-12:]))
    if on_progress:
        on_progress(frames, frames)
    return out_mp4
