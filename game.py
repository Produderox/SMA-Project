from __future__ import annotations  
from typing import List, Tuple,Callable
from shoe import Shoe, Card


# card-related helpers -------------------------------------------------------
VALUES = {
    "A": 1,  # Ace is special, treated as 1 or 11 in hand logic
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
}

# simple mapping from suit name to a single-character symbol for display
_SUITSYM = {"hearts": "♥", "diamonds": "♦", "clubs": "♣", "spades": "♠"}


def card_str(card: Card) -> str:
    """Return a human-readable string for a card, e.g. 'A♠'."""
    rank, suit = card
    sym = _SUITSYM.get(suit, suit)
    return f"{rank}{sym}"


class Hand:
    """Represents a hand of cards for a player or the dealer.

    The class provides utilities to add cards and compute possible totals taking
    aces into account.  It can also report whether the hand is a blackjack,
    whether it has busted, or whether it is "soft" (contains an ace counted as
    11).
    """

    def __init__(self, cards: List[Card] | None = None) -> None:
        self.cards: List[Card] = cards.copy() if cards is not None else []

    def add_card(self, card: Card) -> None:
        self.cards.append(card)

    def _base_value(self) -> int:
        return sum(VALUES[rank] for rank, _ in self.cards)

    def values(self) -> List[int]:
        """Return all distinct hand totals accounting for aces.

        Example: ['A','7'] -> [8, 18]
        """
        total = self._base_value()
        aces = sum(1 for rank, _ in self.cards if rank == "A")
        values = {total}
        # each ace can optionally add 10 (treating it as 11 instead of 1)
        for _ in range(aces):
            # for each ace we can convert one of the 1s to 11 (+10)
            values |= {v + 10 for v in values}
        return sorted(values)

    def best_value(self) -> int:
        """Return the highest non-busting total, or the smallest total if bust."""
        vals = [v for v in self.values() if v <= 21]
        return max(vals) if vals else min(self.values())

    def is_blackjack(self) -> bool:
        return len(self.cards) == 2 and 21 in self.values()

    def is_bust(self) -> bool:
        return all(v > 21 for v in self.values())

    def is_soft(self) -> bool:
        # a hand is soft if it has an ace counted as 11 without busting and
        # the best value is less than 21. A natural blackjack is *not* treated 
        # as soft for the purposes of dealer decision-making or this helper.
        if self.is_blackjack():
            return False
        best = self.best_value()
        # soft only applies when best value is < 21 and differs from base
        return best < 21 and best != self._base_value()

    def __repr__(self) -> str:
        return f"Hand({self.cards})"

    def __str__(self) -> str:
        """A nicer string when printing a hand."""
        if not self.cards:
            return "<empty>"
        return ", ".join(card_str(c) for c in self.cards)


class BlackjackGame:
    """Core game engine for a single-player blackjack session.

    Configuration parameters control the number of decks, shoe penetration
    level (fraction of cards to deal before reshuffle), dealer behaviour on
    soft 17, and blackjack payout ratio.
    """

    def __init__(
        self,
        num_decks: int,
        penetration: float,
        dealer_hits_soft17: bool,
        blackjack_payout: float,
    ) -> None:
        assert 0 < penetration < 1, "penetration must be between 0 and 1"

        self.num_decks = num_decks
        self.penetration = penetration
        self.dealer_hits_soft17 = dealer_hits_soft17
        self.blackjack_payout = blackjack_payout

        self.shoe = Shoe(num_decks)
        self._initial_count = num_decks * 52
        self._reshuffle_threshold = int(self._initial_count * (1 - penetration))
        # threshold should be at least 1 card; with extreme penetrations the
        # calculation above can produce zero which leads to the shoe being
        # emptied in the middle of a round.  Enforce a minimum of one.
        if self._reshuffle_threshold < 1:
            self._reshuffle_threshold = 1

    def _check_reshuffle(self) -> None:
        if self.shoe.cards_left <= self._reshuffle_threshold:
            self.shoe.reset()

    def _draw(self, count: int = 1) -> List[Card]:
        """Draw cards, reshuffling first if the shoe doesn't have enough left."""
        if self.shoe.cards_left < count:
            self.shoe.reset()
        return self.shoe.draw(count)

    def deal_initial(self) -> Tuple[Hand, Hand]:
        player = Hand()
        dealer = Hand()
        # deal two cards each, alternating
        for _ in range(2):
            player.add_card(self._draw(1)[0])
            dealer.add_card(self._draw(1)[0])
        return player, dealer

    def dealer_play(self, dealer_hand: Hand) -> None:
        """Drive the dealer's hand according to the configured rules."""
        while True:
            value = dealer_hand.best_value()
            soft = dealer_hand.is_soft()
            if value < 17:
                dealer_hand.add_card(self._draw(1)[0])
                continue
            if value == 17 and soft and self.dealer_hits_soft17:
                dealer_hand.add_card(self._draw(1)[0])
                continue
            break

    def play_round(self, bet: float = 1.0) -> float:
        """Play a single betting round, returning net win (positive) or loss.

        A push returns 0. Blackjacks pay according to `blackjack_payout`.
        """
        self._check_reshuffle()
        player_hand, dealer_hand = self.deal_initial()

        # immediate blackjack checks
        player_black = player_hand.is_blackjack()
        dealer_black = dealer_hand.is_blackjack()
        if player_black or dealer_black:
            if player_black and not dealer_black:
                return bet * self.blackjack_payout
            elif dealer_black and not player_black:
                return -bet
            else:
                return 0.0

        # for now assume player stands immediately; later hit/stand logic goes here
        self.dealer_play(dealer_hand)

        if player_hand.is_bust():
            return -bet
        if dealer_hand.is_bust():
            return bet

        player_val = player_hand.best_value()
        dealer_val = dealer_hand.best_value()
        if player_val > dealer_val:
            return bet
        elif player_val < dealer_val:
            return -bet
        else:
            return 0.0
 
    def cards_remaining(self) -> int:
        return self.shoe.cards_left

    # --- strategy helpers --------------------------------------------------

    def play_with_strategy(
        self, strategy: "Callable[..., str]", bet: float = 1.0
    ) -> float:
        """Play a round where the player follows `strategy`.

        The strategy callable receives the player's hand and the dealer's
        upcard and should return one of the actions:
        ``'hit'``, ``'stand'``, ``'double'``, ``'split'`` or ``'surrender'``.

        Strategy implementations may also accept the optional boolean
        parameters ``can_double``, ``can_split`` and ``can_surrender``
        (all default to ``True``/``False``) to decide whether a particular
        play is legal; these are passed automatically below.  The game engine
        applies the consequences of each action, adjusting bets when the
        player doubles, creating additional hands when splitting, and
        terminating the round early on surrender.
        """
        self._check_reshuffle()
        player_hand, dealer_hand = self.deal_initial()

        # immediate blackjack handling (same as play_round)
        player_black = player_hand.is_blackjack()
        dealer_black = dealer_hand.is_blackjack()
        if player_black or dealer_black:
            if player_black and not dealer_black:
                return bet * self.blackjack_payout
            elif dealer_black and not player_black:
                return -bet
            else:
                return 0.0

        # maintain a list of active player hands and their bets; splitting
        # adds new entries.  The index ``i`` walks through the list sequentially.
        hands: List[Hand] = [player_hand]
        bets: List[float] = [bet]
        i = 0
        while i < len(hands):
            hand = hands[i]
            # if the hand is already bust we simply skip it
            if hand.is_bust():
                i += 1
                continue

            # determine what actions the strategy is allowed to consider
            can_double = len(hand.cards) == 2
            can_split = len(hand.cards) == 2 and hand.cards[0][0] == hand.cards[1][0]
            can_surrender = len(hand.cards) == 2
            # some simple strategies (used in earlier tests) only accept two
            # parameters; try the full call first and fall back gracefully.
            try:
                action = strategy(
                    hand,
                    dealer_hand.cards[0],
                    can_double,
                    can_split,
                    can_surrender,
                )
            except TypeError:
                action = strategy(hand, dealer_hand.cards[0])

            if action == "hit":
                hand.add_card(self._draw(1)[0])
                # continue playing the same hand
                continue
            elif action == "stand":
                i += 1
                continue
            elif action == "double":
                # only allowed on two-card hands; if strategy returns this
                # illegally we treat it as a stand.
                if can_double:
                    hand.add_card(self._draw(1)[0])
                    bets[i] *= 2
                i += 1
                continue
            elif action == "split":
                if can_split and len(hands) < 4:
                    # break the pair into two single-card hands
                    rank = hand.cards[0]
                    new1 = Hand([rank])
                    new2 = Hand([rank])
                    new1.add_card(self._draw(1)[0])
                    new2.add_card(self._draw(1)[0])
                    # replace current hand with first split, insert second
                    hands[i] = new1
                    hands.insert(i + 1, new2)
                    bets.insert(i + 1, bets[i])
                    # do not advance ``i`` so we immediately act on the first
                    # split hand.
                    continue
                else:
                    i += 1
                    continue
            elif action == "surrender":
                if can_surrender:
                    return -bets[i] / 2
                else:
                    i += 1
                    continue
            else:
                raise ValueError(f"unknown action {action!r}")

        # once all player hands are complete, play out the dealer normally
        self.dealer_play(dealer_hand)

        # now evaluate each hand against the dealer's final total
        net = 0.0
        for hand, hbet in zip(hands, bets):
            if hand.is_bust():
                net -= hbet
            elif dealer_hand.is_bust():
                net += hbet
            else:
                pv = hand.best_value()
                dv = dealer_hand.best_value()
                if pv > dv:
                    net += hbet
                elif pv < dv:
                    net -= hbet
                # pushes yield zero
        return net

    def simulate(
        self,
        strategy: "Callable[..., str]",
        rounds: int = 100000,
    ) -> float:
        """Run a number of rounds returning average net per bet.

        ``strategy`` may accept either two parameters (hand, upcard) or the
        extended five-argument form documented in ``play_with_strategy``.
        """
        total = 0.0
        for _ in range(rounds):
            total += self.play_with_strategy(strategy)
        return total / rounds

    def simulate_counting(
        self,
        play_strategy: "Callable[..., str]",
        count_function: "Callable[[Card], int]",
        bet_function: "Callable[[int, float], float]",
        rounds: int = 100000,
    ) -> float:
        """Run a number of rounds using a running count to size bets.

        ``count_function`` converts each card to a count increment.
        ``bet_function`` receives the current running count and an estimate of
        decks remaining and returns the wager for the upcoming hand.  The
        running count is reset whenever the shoe is reshuffled.
        """
        total = 0.0
        running_count = 0

        # wrap the shoe.reset method to also reset the running count
        orig_reset = self.shoe.reset

        def counting_reset():
            nonlocal running_count
            running_count = 0
            orig_reset()

        self.shoe.reset = counting_reset

        # similarly wrap _draw to update the running count
        orig_draw = self._draw

        def counting_draw(count: int = 1) -> List[Card]:
            nonlocal running_count
            cards = orig_draw(count)
            for card in cards:
                running_count += count_function(card)
            return cards

        self._draw = counting_draw

        try:
            for _ in range(rounds):
                decks_left = self.shoe.cards_left / 52
                bet = bet_function(running_count, decks_left)
                total += self.play_with_strategy(play_strategy, bet=bet)
        finally:
            # restore original methods
            self._draw = orig_draw
            self.shoe.reset = orig_reset

        return total / rounds

    def __repr__(self) -> str:
        return (
            f"<BlackjackGame decks={self.num_decks} "
            f"penetration={self.penetration} "
            f"cards_left={self.cards_remaining()}>"
        )
