import random
from typing import List, Tuple

Rank = str
Suit = str
Card = Tuple[Rank, Suit]


class Shoe:
    """Represents a blackjack shoe containing multiple decks of cards.

    The default configuration uses 6 decks but this can be adjusted by passing
    a different `num_decks` value at initialization. The shoe provides methods
    to shuffle, draw cards, and check how many remain.
    """

    _RANKS: List[Rank] = [
        "A",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "J",
        "Q",
        "K",
    ]
    _SUITS: List[Suit] = ["hearts", "diamonds", "clubs", "spades"]

    def __init__(self, num_decks: int = 6) -> None:
        self.num_decks = num_decks
        self._cards: List[Card] = []
        self.reset()

    def reset(self) -> None:
        """Populate the shoe with `num_decks` worth of cards and shuffle.

        After a reset the shoe behaves as if freshly loaded from the box.
        """
        self._cards = []
        for _ in range(self.num_decks):
            for suit in Shoe._SUITS:
                for rank in Shoe._RANKS:
                    self._cards.append((rank, suit))
        self.shuffle()

    def shuffle(self) -> None:
        """Randomly shuffle the cards in the shoe."""
        random.shuffle(self._cards)

    def draw(self, count: int = 1) -> List[Card]:
        """Draw one or more cards from the top of the shoe.

        Returns a list of `(rank, suit)` tuples in the order they were removed.
        If the requested number of cards is not available, a ValueError is raised.
        """
        if count < 1:
            raise ValueError("Must draw at least one card")
        if count > len(self._cards):
            raise ValueError("Not enough cards left in the shoe to draw")

        drawn = self._cards[:count]
        self._cards = self._cards[count:]
        return drawn

    @property
    def cards_left(self) -> int:
        """Number of remaining cards in the shoe."""
        return len(self._cards)

    def __len__(self) -> int:
        return self.cards_left

    def __repr__(self) -> str:
        return f"<Shoe decks={self.num_decks} cards_left={self.cards_left}>"
