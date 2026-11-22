from pitwall.radio import lap_of, tags


def test_tags_whole_words_and_case():
    assert tags("Box box, box this lap") == {"box"}
    assert tags("The rears are gone, no grip") == {"tyres"}
    assert tags("Boxer shorts") == set()  # not a whole word
    assert tags("Push now, gap is 1.2") == {"pace"}
    assert tags("We have a gearbox problem") == {"issue"}
    assert tags("") == set()


def test_lap_of_takes_the_last_start_before_the_clip():
    starts = [("2023-04-02T05:00:00", 1), ("2023-04-02T05:01:30", 2), ("2023-04-02T05:03:00", 3)]
    assert lap_of("2023-04-02T05:02:00", starts) == 2
    assert lap_of("2023-04-02T05:03:00", starts) == 3
    assert lap_of("2023-04-02T04:59:00", starts) is None
