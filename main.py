from game import BlackjackGame

def main() -> None:
    from strategy import basic_strategy
    
    # Configuration
    num_decks = 6
    penetration = 0.75
    dealer_hits_soft17 = False
    blackjack_payout = 1.5
    rounds = 10000000
    
    game = BlackjackGame(
        num_decks=num_decks,
        penetration=penetration,
        dealer_hits_soft17=dealer_hits_soft17,
        blackjack_payout=blackjack_payout,
    )
    print(f"Simulating {rounds} rounds with full basic strategy...")
    avg = game.simulate(basic_strategy, rounds=rounds)
    print(f"House edge: {-avg*100:.3f}%")


if __name__ == "__main__":
    main()
