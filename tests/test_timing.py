from shorts.timing import build_cues, total_duration, even_words


def test_cues_are_sequential_with_gap_lead_in_and_punch_gap():
    cues = build_cues([1.0, 2.0], ["a", "b c"], ["reporter", "animal"], gap=0.25, lead_in=0.6, punch_gap=0.5)
    assert (cues[0].start, cues[0].end) == (0.6, 1.6)
    assert (cues[1].start, cues[1].end) == (2.35, 4.35)  # 마지막 줄 앞 0.5초 뜸
    assert cues[1].speaker == "animal" and cues[1].punch and not cues[0].punch
    assert total_duration(cues, tail=0.6) == 4.95


def test_words_are_absolute_and_fall_back_to_even_split():
    cues = build_cues([1.0, 1.0], ["가나 다", "라"], ["reporter", "animal"],
                      words=[[(0.1, 0.5, "가나"), (0.6, 0.9, "다")], None], punch_gap=0.0)
    assert [(w.start, w.end, w.text) for w in cues[0].words] == [(0.7, 1.1, "가나"), (1.2, 1.5, "다")]
    assert [w.text for w in cues[1].words] == ["라"]


def test_even_words_splits_by_char_count():
    ws = even_words("가 나다", 3.0)
    assert [w[2] for w in ws] == ["가", "나다"] and abs(ws[0][1] - 1.0) < 0.01 and ws[1][1] == 3.0
