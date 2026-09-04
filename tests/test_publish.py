from shorts.publish.youtube import build_video_body
from shorts.publish.media_host import CopyDirHost
from shorts.publish.instagram import publish_reel
from shorts.script_gen import PlaceholderScriptProvider


def test_youtube_body_has_shorts_tag_and_privacy():
    s = PlaceholderScriptProvider().generate("x")
    body = build_video_body(s, "private")
    assert body["snippet"]["title"].endswith("#Shorts")
    assert body["snippet"]["categoryId"] == "15" and body["status"]["privacyStatus"] == "private"
    assert body["status"]["selfDeclaredMadeForKids"] is False
    assert "#ai동물영상" in body["snippet"]["description"]


def test_copydir_host_copies_and_returns_url(tmp_path):
    src = tmp_path / "final.mp4"
    src.write_bytes(b"x")
    url = CopyDirHost(tmp_path / "www", "https://example.com/videos/").upload(src)
    assert url == "https://example.com/videos/final.mp4" and (tmp_path / "www" / "final.mp4").exists()


class FakeResp:
    def __init__(self, data):
        self._d, self.status_code = data, 200

    def json(self):
        return self._d


class FakeSession:
    def __init__(self):
        self.calls, self.polls = [], 0

    def post(self, url, data=None, timeout=None):
        self.calls.append(("POST", url, data))
        return FakeResp({"id": "C1" if url.endswith("/media") else "M9"})

    def get(self, url, params=None, timeout=None):
        self.polls += 1
        return FakeResp({"status_code": "IN_PROGRESS" if self.polls < 2 else "FINISHED"})


def test_publish_reel_creates_polls_publishes():
    sess = FakeSession()
    mid = publish_reel("123", "tok", "https://h/v.mp4", "cap", session=sess, sleep=lambda s: None)
    assert mid == "M9"
    assert sess.calls[0][1].endswith("/123/media") and sess.calls[0][2]["media_type"] == "REELS"
    assert sess.calls[-1][1].endswith("/123/media_publish") and sess.calls[-1][2]["creation_id"] == "C1"
