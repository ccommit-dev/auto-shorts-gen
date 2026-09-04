from shorts.timing import build_cues, total_duration


def test_cues_are_sequential_with_gap_and_lead_in():
    cues = build_cues([1.0, 2.0], ["a", "b"], ["reporter", "animal"], gap=0.25, lead_in=0.6)
    assert (cues[0].start, cues[0].end) == (0.6, 1.6)
    assert (cues[1].start, cues[1].end) == (1.85, 3.85)
    assert cues[1].speaker == "animal"
    assert total_duration(cues, tail=0.6) == 4.45
