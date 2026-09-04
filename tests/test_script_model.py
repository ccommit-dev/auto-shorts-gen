import json
import pytest
from shorts.script_model import Script, slugify

GOOD = {"title": "장사 잘하는법", "character": "하얀 비숑 말순이",
        "scene_prompt": "bichon frise selling roasted chestnuts",
        "lines": [{"speaker": "reporter", "text": "군밤 얼마예요?"},
                  {"speaker": "animal", "text": "예쁜 언니 천원"},
                  {"speaker": "animal", "text": "못생긴 언니 오백원"}],
        "hashtags": ["#ai동물영상", "#강아지"]}


def test_from_json_strips_code_fence_and_validates():
    fenced = "```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```"
    s = Script.from_json(fenced, topic="군밤")
    assert s.topic == "군밤" and s.title == "장사 잘하는법"
    assert [l.speaker for l in s.lines] == ["reporter", "animal", "animal"]


def test_validate_rejects_too_few_lines():
    bad = dict(GOOD, lines=GOOD["lines"][:2])
    with pytest.raises(ValueError):
        Script.from_dict(bad, topic="x")


def test_validate_normalizes_unknown_speaker_to_animal():
    d = dict(GOOD, lines=GOOD["lines"] + [{"speaker": "dog", "text": "멍"}])
    s = Script.from_dict(d, topic="x")
    assert s.lines[-1].speaker == "animal"


def test_hashtags_get_hash_prefix():
    d = dict(GOOD, hashtags=["강아지", "#고양이"])
    assert Script.from_dict(d, topic="x").hashtags == ["#강아지", "#고양이"]


def test_roundtrip_to_dict():
    s = Script.from_dict(GOOD, topic="t")
    assert Script.from_dict(s.to_dict()).topic == "t"


def test_slugify_keeps_hangul_and_limits_length():
    assert slugify("장사 잘하는법! ver.2") == "장사_잘하는법_ver_2"
    assert len(slugify("가" * 100)) <= 30
