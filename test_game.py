from game import Hand, BlackjackGame
from strategy import high_lo_count
from shoe import Card


def make_card(rank: str, suit: str = "hearts") -> Card:
    return (rank, suit)


def test_hand_values_and_blackjack():
    h = Hand([make_card("A"), make_card("7")])
    assert h.values() == [8, 18]
    assert h.best_value() == 18
    assert h.is_soft()
    assert not h.is_bust()
    assert not h.is_blackjack()

    h2 = Hand([make_card("A"), make_card("K")])
    assert h2.is_blackjack()
    assert not h2.is_soft()

    h3 = Hand([make_card("K"), make_card("Q"), make_card("2")])
    assert h3.best_value() == 22
    assert h3.is_bust()


def test_dealer_behavior_soft17():
    # Build a game where we control the shoe order. We'll craft a shoe such that
    # the dealer receives A-6 (soft 17) and then a 5 to force a hit.
    game = BlackjackGame(num_decks=1, penetration=0.99, dealer_hits_soft17=True, blackjack_payout=1.5)
    # place cards on top: player cards (ignored), dealer cards, hit card, then others
    # order: player1, dealer1, player2, dealer2, next hit, ...
    # include an extra card so the dealer can continue hitting if needed
    # include an extra card so the dealer can continue hitting if needed
    game.shoe._cards = [
        make_card("5"),  # player card
        make_card("A"),
        make_card("K"),
        make_card("6"),  # dealer soft-17
        make_card("5"),  # first hit
    ] + [make_card("2")] * 10  # plenty of filler for repeated hits
    # draw initial, then dealer_play should cause additional draws until the
    # dealer reaches 17 or higher (soft rules may cause multiple hits).
    player, dealer = game.deal_initial()
    assert dealer.values() == [7, 17]
    game.dealer_play(dealer)
    # dealer should have at least one extra card and end up with value >=17
    assert len(dealer.cards) >= 3
    assert dealer.best_value() >= 17

    # now test that setting dealer_hits_soft17=False results in stand
    game2 = BlackjackGame(num_decks=1, penetration=0.99, dealer_hits_soft17=False, blackjack_payout=1.5)
    game2.shoe._cards = [
        make_card("5"),
        make_card("A"),
        make_card("K"),
        make_card("6"),
    ]
    p2, d2 = game2.deal_initial()
    assert d2.values() == [7, 17]
    game2.dealer_play(d2)
    assert len(d2.cards) == 2


def test_reshuffle_triggered():
    game = BlackjackGame(num_decks=1, penetration=0.5, dealer_hits_soft17=True, blackjack_payout=1.5)
    # force shoe to have exactly threshold cards left
    game.shoe._cards = [make_card("5")] * game._reshuffle_threshold
    assert game.shoe.cards_left == game._reshuffle_threshold
    game._check_reshuffle()
    # after check, shoe should have been reset to full deck size
    assert game.shoe.cards_left == 52


def test_play_round_outcomes():
    game = BlackjackGame(num_decks=1, penetration=0.99, dealer_hits_soft17=True, blackjack_payout=1.5)
    # win scenario: player 20 vs dealer 18
    game.shoe._cards = [
        make_card("10"),
        make_card("9"),
        make_card("K"),
        make_card("8"),
    ] + [make_card("2")] * 10  # filler to allow dealer hits
    result = game.play_round(bet=10)
    assert result == 10

    # push scenario (same value)
    # make both hands total 20 for a push
    game.shoe._cards = [
        make_card("K"),
        make_card("10"),
        make_card("Q"),
        make_card("10"),
    ] + [make_card("2")] * 10
    assert game.play_round(bet=5) == 0

    # loss scenario (player 17 vs dealer 19)
    game.shoe._cards = [
        make_card("10"),
        make_card("9"),
        make_card("7"),
        make_card("K"),
    ] + [make_card("2")] * 10
    assert game.play_round(bet=2) == -2

    # ensure card_str helper prints succinct value
    from game import card_str
    assert card_str(make_card("A", "spades")) == "A♠"

    # player blackjack pays 1.5x (dealer not blackjack)
    game.shoe._cards = [
        make_card("A"),
        make_card("9"),
        make_card("K"),
        make_card("5"),
    ] + [make_card("2")] * 5
    assert game.play_round(bet=4) == 4 * 1.5

    # play_with_strategy: use naive always-stand strategy; should match play_round
    def stand_strategy(hand, upcard):
        return "stand"
    game.shoe._cards = [
        make_card("10"),
        make_card("9"),
        make_card("K"),
        make_card("8"),
    ] + [make_card("2")] * 5
    result1 = game.play_with_strategy(stand_strategy, bet=5)
    # reset the shoe to the same order and compare
    game.shoe._cards = [
        make_card("10"),
        make_card("9"),
        make_card("K"),
        make_card("8"),
    ] + [make_card("2")] * 5
    assert result1 == game.play_round(bet=5)

    # simulate with stand strategy should return a finite value
    avg = game.simulate(stand_strategy, rounds=100)
    assert isinstance(avg, float)

    # simulation with full basic strategy should produce a small house edge
    from strategy import basic_strategy
    avg2 = game.simulate(basic_strategy, rounds=2000)
    # with doubling/splitting enabled the edge should be very close to
    # zero.  We don't require a particular sign because a few thousand
    # rounds can easily fluctuate either way.
    assert abs(avg2) < 0.1

    # both blackjack -> push
    game.shoe._cards = [
        make_card("A"),
        make_card("A"),
        make_card("K"),
        make_card("K"),
    ]
    assert game.play_round(bet=3) == 0


def test_play_with_strategy_double_action():
    game = BlackjackGame(num_decks=1, penetration=0.99, dealer_hits_soft17=True, blackjack_payout=1.5)
    # sequence: player 5 vs 6, player 5 vs 9, double card 10 -> player 20, dealer hit 9 busts
    game.shoe._cards = [
        make_card("5"), make_card("6"),
        make_card("5"), make_card("9"),
        make_card("10"), make_card("9"),
    ]

    def always_double(hand, upcard, can_double, can_split, can_surrender):
        return "double"

    # initial bet 1, doubled, player wins both units
    assert game.play_with_strategy(always_double, bet=1) == 2


def test_play_with_strategy_split_action():
    game = BlackjackGame(num_decks=1, penetration=0.99, dealer_hits_soft17=True, blackjack_payout=1.5)
    # sequence: player 8 vs 5, player 8 vs K, split draws 10 and 9, dealer hits 9 bust
    game.shoe._cards = [
        make_card("8"), make_card("5"),
        make_card("8"), make_card("K"),
        make_card("10"), make_card("9"),
        make_card("9"),
    ]

    def split_once(hand, upcard, can_double, can_split, can_surrender):
        return "split" if can_split else "stand"

    # after splitting two winning hands => net +2
    assert game.play_with_strategy(split_once, bet=1) == 2


def test_play_with_strategy_surrender_action():
    game = BlackjackGame(num_decks=1, penetration=0.99, dealer_hits_soft17=True, blackjack_payout=1.5)
    game.shoe._cards = [make_card("2"), make_card("3"), make_card("4"), make_card("5")]

    def always_surrender(hand, upcard, can_double, can_split, can_surrender):
        return "surrender"

    assert game.play_with_strategy(always_surrender, bet=10) == -5


def test_simulate_counting_bets_change():
    # create small shoe where cards drawn are all low (high count)
    game = BlackjackGame(num_decks=1, penetration=0.99, dealer_hits_soft17=True, blackjack_payout=1.5)
    # we will supply 12 cards (3 rounds x 4 cards) all low to push count up
    game.shoe._cards = [
        make_card("2"), make_card("3"), make_card("4"), make_card("5"),
        make_card("2"), make_card("3"), make_card("4"), make_card("5"),
        make_card("2"), make_card("3"), make_card("4"), make_card("5"),
    ]
    bet_history: list[float] = []

    def bet_fn(rc, decks):
        b = min(12, 1 + max(0, rc))
        bet_history.append(b)
        return b

    # use simple stand strategy to avoid extra draws
    def stand(hand, upcard, *args, **kwargs):
        return "stand"

    avg = game.simulate_counting(stand, high_lo_count, bet_fn, rounds=3)
    # since cards are low, running count increases steadily -> bets should escalate
    assert bet_history[0] == 1
    # at least one of the subsequent bets should differ, showing that
    # running count influenced the wager size
    assert len(bet_history) == 3
    assert any(b != bet_history[0] for b in bet_history[1:])

    # also verify average returned is finite
    assert isinstance(avg, float)
