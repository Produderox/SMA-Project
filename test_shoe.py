import pytest

from shoe import Shoe


def test_default_shoe_size():
    shoe = Shoe()
    # 6 decks * 52 cards each
    assert shoe.cards_left == 6 * 52


def test_shuffle_changes_order():
    shoe = Shoe()
    before = shoe._cards.copy()
    shoe.shuffle()
    # It's possible shuffle leaves order unchanged by randomness,
    # but extremely unlikely; check not equal to catch typical failures.
    assert shoe._cards != before


def test_draw_reduces_cards():
    shoe = Shoe()
    initial = shoe.cards_left
    drawn = shoe.draw(3)
    assert len(drawn) == 3
    assert shoe.cards_left == initial - 3


def test_draw_too_many_raises():
    shoe = Shoe(num_decks=1)
    with pytest.raises(ValueError):
        shoe.draw(53)


def test_reset_restores_full_shoe():
    shoe = Shoe()
    shoe.draw(10)
    assert shoe.cards_left < 6 * 52
    shoe.reset()
    assert shoe.cards_left == 6 * 52
