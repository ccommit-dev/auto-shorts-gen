import io
from PIL import Image
from shorts.image_gen import fit_portrait, PlaceholderImageProvider, LocalImageProvider, PollinationsImageProvider, PORTRAIT
from shorts.config import Settings
from shorts.usage_ledger import UsageLedger


def test_fit_portrait_cover_crops_to_1080x1920():
    assert fit_portrait(Image.new("RGB", (400, 300))).size == PORTRAIT
    assert fit_portrait(Image.new("RGB", (300, 900))).size == PORTRAIT


def test_placeholder_writes_portrait_png(tmp_path):
    p = PlaceholderImageProvider().generate("dog", tmp_path / "scene.png")
    assert Image.open(p).size == PORTRAIT


def test_local_provider_fits_source(tmp_path):
    src = tmp_path / "src.jpg"
    Image.new("RGB", (640, 480), "red").save(src)
    p = LocalImageProvider(src).generate("ignored", tmp_path / "scene.png")
    assert Image.open(p).size == PORTRAIT


class FakeResp:
    def __init__(self, status, content_type, body):
        self.status_code, self.headers, self.content = status, {"content-type": content_type}, body


class FakeSession:
    def __init__(self, resp):
        self.resp, self.calls = resp, []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.resp


def test_pollinations_uses_ledger_and_saves(tmp_path):
    buf = io.BytesIO()
    Image.new("RGB", (576, 1024), "blue").save(buf, "JPEG")
    sess = FakeSession(FakeResp(200, "image/jpeg", buf.getvalue()))
    led = UsageLedger(tmp_path / "u.json")
    prov = PollinationsImageProvider(Settings(), led, session=sess)
    p = prov.generate("a cute dog", tmp_path / "scene.png")
    assert Image.open(p).size == PORTRAIT and led.count("pollinations") == 1
    assert "a%20cute%20dog" in sess.calls[0][0] and sess.calls[0][1]["width"] == 1080


def test_pollinations_appends_style_suffix_and_fixed_seed(tmp_path):
    buf = io.BytesIO()
    Image.new("RGB", (576, 1024), "blue").save(buf, "JPEG")
    sess = FakeSession(FakeResp(200, "image/jpeg", buf.getvalue()))
    s = Settings(image_seed=77, image_style_suffix="mouth closed, looking at the camera")
    PollinationsImageProvider(s, UsageLedger(tmp_path / "u.json"), session=sess).generate("a dog", tmp_path / "s.png")
    url, params = sess.calls[0]
    assert "mouth%20closed" in url and params["seed"] == 77
