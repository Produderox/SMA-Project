from strategy import basic_strategy, high_lo_count, bet_spread
from shoe import Card
from game import Hand


def make_card(rank: str, suit: str = "hearts") -> Card:
    return (rank, suit)


def test_basic_split_logic():
    up = make_card("5")
    # pairs that should split
    for r in ["A", "8", "2", "3", "6", "7", "9"]:
        h = Hand([make_card(r), make_card(r)])
        assert basic_strategy(h, up, can_split=True).startswith("split")
    # 5s should not split
    h5 = Hand([make_card("5"), make_card("5")])
    assert basic_strategy(h5, up, can_split=True) != "split"


def test_basic_soft_and_hard():
    # soft 18 vs 9 should hit
    h = Hand([make_card("A"), make_card("7")])
    assert basic_strategy(h, make_card("9")) == "hit"
    # hard 12 vs 4 should stand
    h2 = Hand([make_card("10"), make_card("2")])
    assert basic_strategy(h2, make_card("4")) == "stand"


def test_double_conditions():
    # hard 11 always double
    h = Hand([make_card("6"), make_card("5")])
    assert basic_strategy(h, make_card("K"), can_double=True) == "double"
    # soft A-5 vs 5 should double
    h2 = Hand([make_card("A"), make_card("5")])
    assert basic_strategy(h2, make_card("5"), can_double=True) == "double"


def test_surrender_rule():
    # 15 vs 10 surrender
    h = Hand([make_card("10"), make_card("5")])
    assert basic_strategy(h, make_card("10"), can_surrender=True) == "surrender"


def test_high_lo_count_values():
    # low cards +1, neutral 0, high -1
    assert high_lo_count(make_card("2")) == 1
    assert high_lo_count(make_card("6")) == 1
    assert high_lo_count(make_card("7")) == 0
    assert high_lo_count(make_card("9")) == 0
    assert high_lo_count(make_card("10")) == -1
    assert high_lo_count(make_card("A")) == -1


def test_bet_spread_mapping():
    # with one deck remaining
    assert bet_spread(0, 1) == 1
    assert bet_spread(1, 1) == 1
    assert bet_spread(2, 1) == 2
    assert bet_spread(11, 1) == 11
    assert bet_spread(20, 1) == 12  # capped at spread_max
    # with two decks remaining, running count 4 gives true count 2 -> bet 2
    assert bet_spread(4, 2) == 2
