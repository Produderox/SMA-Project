from __future__ import annotations

import random
from game import Hand, VALUES
from shoe import Card


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def card_value(card: Card) -> int:
    """Convert a card to its numeric value (Ace = 11)."""
    if card[0] == "A":
        return 11
    return int(VALUES[card[0]])


# ---------------------------------------------------------------------------
# Basic Strategy  (S17, 6-deck, late surrender)
# ---------------------------------------------------------------------------

def basic_strategy(
    hand: Hand,
    dealer_upcard: Card,
    can_double: bool = True,
    can_split: bool = True,
    can_surrender: bool = False,
) -> str:
    """Return the correct basic-strategy action."""
    up = card_value(dealer_upcard)

    if can_surrender and len(hand.cards) == 2:
        total = hand.best_value()
        if total == 15 and up == 10:
            return "surrender"
        if total == 16 and up in (9, 10, 11):
            return "surrender"

    if can_split and len(hand.cards) == 2 and hand.cards[0][0] == hand.cards[1][0]:
        rank = hand.cards[0][0]
        if rank in ("10", "J", "Q", "K"):
            rank = "10"
        pair_value = VALUES[rank]
        if pair_value == 1 or pair_value == 8:
            return "split"
        if pair_value in (2, 3) and 2 <= up <= 7:
            return "split"
        if pair_value == 4 and 5 <= up <= 6:
            return "split"
        if pair_value == 6 and 2 <= up <= 6:
            return "split"
        if pair_value == 7 and 2 <= up <= 7:
            return "split"
        if pair_value == 9 and (2 <= up <= 6 or up in (8, 9)):
            return "split"

    total = hand.best_value()
    soft  = hand.is_soft()

    if soft:
        if total >= 19:
            return "stand"
        if total == 18:
            if up >= 9:
                return "hit"
            if up in (3, 4, 5, 6) and can_double:
                return "double"
            return "stand"
        if total == 17:
            if up in (3, 4, 5, 6) and can_double:
                return "double"
            if up == 2:
                return "stand"
            return "hit"
        if total in (16, 15):
            if up in (4, 5, 6) and can_double:
                return "double"
            return "hit"
        if total in (14, 13):
            if up in (5, 6) and can_double:
                return "double"
            return "hit"
        return "hit"
    else:
        if total >= 17:
            return "stand"
        if 13 <= total <= 16:
            return "stand" if 2 <= up <= 6 else "hit"
        if total == 12:
            return "stand" if 4 <= up <= 6 else "hit"
        if total == 11 and can_double:
            return "double"
        if total == 10 and can_double and up <= 9:
            return "double"
        if total == 9 and can_double and 3 <= up <= 6:
            return "double"
        return "hit"


# ---------------------------------------------------------------------------
# Gambler Strategy – gut-feel deviations
# ---------------------------------------------------------------------------

_GAMBLER_MISTAKES = [
    (lambda t, u, s, cd, cs: not s and t == 16 and u >= 7, "stand",
     "stands 16 vs high card — afraid to bust"),
    (lambda t, u, s, cd, cs: not s and t == 15 and u >= 7, "stand",
     "stands 15 vs high card — gut says stay"),
    (lambda t, u, s, cd, cs: not s and t == 11 and cd, "hit",
     "won't double 11 — too nervous"),
    (lambda t, u, s, cd, cs: not s and t == 10 and u <= 6 and cd, "hit",
     "won't double 10 — superstition"),
    (lambda t, u, s, cd, cs: s and t == 18 and 3 <= u <= 6 and cd, "stand",
     "stands soft 18 vs 3-6 — thinks 18 is good enough"),
    (lambda t, u, s, cd, cs: cs and t == 16 and u >= 9, "stand",
     "won't split 8-8 vs 9+ — refuses to double up"),
    (lambda t, u, s, cd, cs: cs and t == 12 and s, "hit",
     "won't split Aces — afraid to ruin soft 12"),
    (lambda t, u, s, cd, cs: not s and t == 12 and u in (2, 3), "stand",
     "stands 12 vs 2-3 — thinks dealer busts"),
    (lambda t, u, s, cd, cs: not s and 13 <= t <= 16 and 2 <= u <= 6, "hit",
     "hits stiff hand vs weak dealer — impatient"),
    (lambda t, u, s, cd, cs: cs and not s and t == 20, "split",
     "splits tens — greedily wants two hands"),
    (lambda t, u, s, cd, cs: s and t == 17 and u >= 7 and cd, "double",
     "doubles soft 17 vs strong dealer — overconfident"),
    (lambda t, u, s, cd, cs: not s and t == 15 and u >= 8, "surrender",
     "surrenders 15 vs 8+ — gives up too easily"),
]


def _gut_feel_action(total, up, soft, can_double, can_split, available):
    applicable = [
        (wrong, note)
        for cond, wrong, note in _GAMBLER_MISTAKES
        if cond(total, up, soft, can_double, can_split) and wrong in available
    ]
    if not applicable:
        return None
    wrong, _ = random.choice(applicable)
    return wrong


def make_gambler_strategy(deviation_rate: float = 0.25):
    """Return a strategy that deviates from basic strategy at the given rate."""
    if not 0.0 <= deviation_rate <= 1.0:
        raise ValueError("deviation_rate must be in [0, 1]")

    def gambler_strategy(
        hand: Hand,
        dealer_upcard: Card,
        can_double: bool = True,
        can_split: bool = True,
        can_surrender: bool = False,
    ) -> str:
        correct = basic_strategy(hand, dealer_upcard, can_double, can_split, can_surrender)
        if random.random() >= deviation_rate:
            return correct

        up    = card_value(dealer_upcard)
        total = hand.best_value()
        soft  = hand.is_soft()
        available = ["hit", "stand"]
        if can_double:
            available.append("double")
        if can_split:
            available.append("split")
        if can_surrender:
            available.append("surrender")

        wrong = _gut_feel_action(total, up, soft, can_double, can_split, available)
        if wrong is None or wrong == correct:
            return correct
        return wrong

    return gambler_strategy


# ---------------------------------------------------------------------------
# High–Low card counting utilities
# ---------------------------------------------------------------------------

def high_lo_count(card: Card) -> int:
    """Hi-Low count: 2-6 → +1, 7-9 → 0, 10-A → -1."""
    rank = card[0]
    if rank in ("2", "3", "4", "5", "6"):
        return 1
    if rank in ("7", "8", "9"):
        return 0
    return -1


def bet_spread(
    run_count: int,
    decks_remaining: float,
    spread_min: int = 1,
    spread_max: int = 12,
) -> int:
    """Convert running count + decks remaining into a bet size."""
    true_count = run_count / max(decks_remaining, 1)
    bet = spread_min
    if true_count > 1:
        bet += int(true_count) - 1
    return min(bet, spread_max)


def bet_spread_with_cover(
    run_count: int,
    decks_remaining: float,
    spread_min: int = 1,
    spread_max: int = 12,
    cover_pct: float = 0.0,
) -> int:
    """
    AP bet spread with cover play — occasionally deliberately flat-bets or
    under-bets the true count signal to reduce bet-correlation detectability.

    cover_pct = 0.0 → pure Hi-Lo (no cover, maximum edge, detectable)
    cover_pct = 0.5 → 50% of rounds the AP randomises their bet downward
    cover_pct = 1.0 → always flat-bets minimum (no edge, perfectly hidden)

    The tradeoff: higher cover_pct → lower house leakage per round but longer
    time before surveillance certainty crosses the ejection threshold.
    """
    if not 0.0 <= cover_pct <= 1.0:
        raise ValueError("cover_pct must be in [0, 1]")

    optimal_bet = bet_spread(run_count, decks_remaining, spread_min, spread_max)

    if random.random() < cover_pct:
        # Cover play: bet a random amount between min and optimal
        # This introduces noise that suppresses Pearson correlation
        cover_bet = random.randint(spread_min, max(spread_min, optimal_bet))
        return cover_bet

    return optimal_bet


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

STRATEGIES = {
    "basic":   basic_strategy,
    "gambler": make_gambler_strategy,
}