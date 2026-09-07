from shorts.script_gen import PlaceholderScriptProvider, build_user_prompt, SYSTEM_PROMPT
from shorts.topics import random_topic


def test_placeholder_script_is_valid():
    s = PlaceholderScriptProvider().generate("강아지 군밤장사")
    assert 3 <= len(s.lines) <= 6 and s.title


def test_prompt_mentions_topic_and_rules():
    assert "강아지 군밤장사" in build_user_prompt("강아지 군밤장사")
    assert "JSON" in SYSTEM_PROMPT


def test_random_topic_is_pet_related():
    t = random_topic()
    assert any(k in t for k in ("강아지", "고양이", "댕댕이", "냥이"))


def test_system_prompt_asks_short_punchline_and_closed_mouth():
    assert "6자 이내" in SYSTEM_PROMPT and "mouth closed" in SYSTEM_PROMPT
