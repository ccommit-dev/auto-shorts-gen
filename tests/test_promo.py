import json

import pytest

from shorts.config import Settings
from shorts.promo.audio import build_mux_args
from shorts.promo.pipeline import as_upload_script, build_timeline, narration_cues, PromoPaths
from shorts.promo.script_gen import PlaceholderPromoScript, build_promo_script_provider
from shorts.promo.spec import PromoScript, Scene, SceneValidationError, plain
from shorts.usage_ledger import UsageLedger


def sample(**over) -> PromoScript:
    s = PlaceholderPromoScript().generate("모코")
    for k, v in over.items():
        setattr(s, k, v)
    return s


def test_plain_strips_markup():
    assert plain("좋은 지식은||[중앙]에 쌓입니다.") == "좋은 지식은 중앙에 쌓입니다."


def test_scene_speech_prefers_narration_then_title_and_body():
    assert Scene(title="[가]나", body="다", narration="읽을 말").speech() == "읽을 말"
    assert Scene(title="[가]나", body="다").speech() == "가나 다"


def test_placeholder_script_is_valid_and_round_trips():
    s = sample()
    again = PromoScript.from_dict(json.loads(json.dumps(s.to_dict())))
    assert [x.kind for x in again.scenes] == [x.kind for x in s.scenes]
    assert again.scenes[0].kind == "cover" and again.scenes[-1].kind == "outro"


def test_from_json_tolerates_code_fence():
    raw = "```json\n" + json.dumps(sample().to_dict(), ensure_ascii=False) + "\n```"
    assert PromoScript.from_json(raw).title


@pytest.mark.parametrize("over, msg", [
    ({"title": ""}, "title"),
    ({"accent": "green"}, "accent"),
    ({"scenes": []}, "장면 수"),
])
def test_validation_rejects_broken_scripts(over, msg):
    with pytest.raises(SceneValidationError) as e:
        sample(**over).validate()
    assert msg in str(e.value)


def test_validation_rejects_unknown_kind_and_empty_items():
    with pytest.raises(SceneValidationError):
        sample(scenes=[Scene("cover", title="가"), Scene("우주선", title="나"), Scene("outro", title="다")]).validate()
    with pytest.raises(SceneValidationError):
        sample(scenes=[Scene("cover", title="가"), Scene("ui", title="나"), Scene("outro", title="다")]).validate()


def test_timeline_follows_narration_length_and_is_contiguous():
    st = Settings(promo_min_scene=2.0, promo_lead=0.5)
    s = sample()
    tl = build_timeline(s, [1.0] * len(s.scenes), st)
    assert len(tl["scenes"]) == len(s.scenes)
    assert tl["scenes"][0]["start"] == 0.0
    for a, b in zip(tl["scenes"], tl["scenes"][1:]):
        assert b["start"] == pytest.approx(a["start"] + a["dur"])
    last = tl["scenes"][-1]
    assert tl["total"] == pytest.approx(last["start"] + last["dur"])


def test_timeline_respects_minimum_scene_length():
    st = Settings(promo_min_scene=9.0, promo_lead=0.5)
    s = sample()
    tl = build_timeline(s, [0.2] * len(s.scenes), st)
    assert all(x["dur"] == 9.0 for x in tl["scenes"])


def test_timeline_grows_with_narration_and_hold():
    st = Settings(promo_min_scene=0.0, promo_lead=0.5)
    s = sample()
    s.scenes[0].hold = 2.0
    tl = build_timeline(s, [3.0] * len(s.scenes), st)
    assert tl["scenes"][0]["dur"] > tl["scenes"][1]["dur"]


def test_narration_starts_after_the_lead(tmp_path):
    st = Settings(promo_lead=0.5)
    s = sample()
    tl = build_timeline(s, [2.0] * len(s.scenes), st)
    cues = narration_cues(tl, PromoPaths(tmp_path), st.promo_lead)
    assert cues[0][0] == 0.5
    assert cues[1][0] == pytest.approx(tl["scenes"][1]["start"] + 0.5)
    assert cues[0][1].name == "vo_00.mp3"


def test_upload_script_adapter_keeps_title_and_hashtags():
    s = sample()
    up = as_upload_script(s)
    assert up.title == s.title and up.hashtags == s.hashtags
    assert "[" not in up.lines[0].text


def test_mux_args_place_each_narration_and_duck_the_bgm(tmp_path):
    args = build_mux_args(tmp_path / "s.mp4", [(0.5, tmp_path / "a.mp3"), (4.25, tmp_path / "b.mp3")],
                          tmp_path / "bgm.mp3", 12.0, tmp_path / "out.mp4", bgm_gain=0.08)
    f = args[args.index("-filter_complex") + 1]
    assert "adelay=500|500" in f and "adelay=4250|4250" in f
    assert "volume=0.080" in f and "loudnorm" in f and "stereo" in f
    assert args[args.index("-t") + 1] == "12.000"
    assert "-stream_loop" in args and args.count("-i") == 4


def test_mux_args_without_bgm_or_narration(tmp_path):
    only_voice = build_mux_args(tmp_path / "s.mp4", [(0.0, tmp_path / "a.mp3")], None, 5.0, tmp_path / "o.mp4")
    assert "-stream_loop" not in only_voice and "amix" not in only_voice[only_voice.index("-filter_complex") + 1]
    silent = build_mux_args(tmp_path / "s.mp4", [], None, 5.0, tmp_path / "o.mp4")
    assert silent[:2] == ["-i", str(tmp_path / "s.mp4")] and "-c" in silent


def test_provider_choice_defaults_to_free_and_blocks_unknown(tmp_path):
    led = UsageLedger(tmp_path / "u.json")
    assert isinstance(build_promo_script_provider(Settings(), led, dry_run=True), PlaceholderPromoScript)
    assert isinstance(build_promo_script_provider(Settings(), led, dry_run=False, provider="placeholder"),
                      PlaceholderPromoScript)
    with pytest.raises(RuntimeError):
        build_promo_script_provider(Settings(), led, dry_run=False, provider="claude")


def test_gemini_promo_provider_needs_a_key(tmp_path):
    from shorts.promo.script_gen import GeminiPromoScript
    with pytest.raises(RuntimeError):
        GeminiPromoScript(Settings(gemini_api_key=None), UsageLedger(tmp_path / "u.json"))


def test_promo_paths_are_under_the_run_dir(tmp_path):
    p = PromoPaths(tmp_path)
    assert p.final_mp4.parent == tmp_path and p.narration_mp3(3).name == "vo_03.mp3"
    assert p.script_json.name == "promo.json" and p.silent_mp4.name == "silent.mp4"
