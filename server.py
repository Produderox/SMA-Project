"""
Blackjack Simulation API Server
Run: python server.py
Requires: flask  (pip install flask)
Place alongside game.py, shoe.py, strategy.py, main.py.
"""

from flask import Flask, jsonify, request
from game import BlackjackGame
from strategy import (
    basic_strategy,
    make_gambler_strategy,
    high_lo_count,
    bet_spread,
    bet_spread_with_cover,
)
import random

app = Flask(__name__)


# ── CORS ───────────────────────────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/options",  methods=["OPTIONS"])
@app.route("/simulate", methods=["OPTIONS"])
def options():
    return "", 204


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_game(cfg: dict) -> BlackjackGame:
    return BlackjackGame(
        num_decks          = int(cfg.get("decks", 6)),
        penetration        = float(cfg.get("penetration", 0.75)),
        dealer_hits_soft17 = bool(cfg.get("dealer_hits_soft17", False)),
        blackjack_payout   = float(cfg.get("blackjack_payout", 1.5)),
    )


def _run_paths(cfg: dict, mode: str) -> dict:
    """
    Simulate path_count independent sessions of `rounds` each.

    mode: "basic" | "hilo" | "gambler" | "ap_cover"

    Returns bankroll snapshots, aggregate stats, AND per-path bet histories
    (sampled every snap_every hands) for use by the casino floor Pearson
    correlation surveillance engine.

    Extra fields returned:
      bet_histories  – list of lists, one per path; each entry is a bet size
                       recorded at the same cadence as the bankroll snapshot.
      true_count_histories – synthetic true-count series at the same cadence;
                       only meaningful for hilo / ap_cover, zeros otherwise.
    """
    rounds         = int(cfg.get("rounds", 10_000))
    path_count     = int(cfg.get("paths",  200))
    start_bk       = float(cfg.get("bankroll", 200))
    snap_every     = max(1, rounds // 100)

    spread_min     = int(cfg.get("spread_min", 1))
    spread_max     = int(cfg.get("spread_max", 12))
    deviation_rate = float(cfg.get("deviation_rate", 0.25))
    cover_pct      = float(cfg.get("cover_pct", 0.0))      # AP cover deviation
    hunch_chance   = float(cfg.get("hunch_chance", 0.0))   # casual hunch bet probability

    if mode == "gambler":
        strategy_fn = make_gambler_strategy(deviation_rate)
    else:
        strategy_fn = basic_strategy

    all_paths         = []
    bet_histories     = []
    tc_histories      = []
    final_bks         = []
    total_net         = 0.0
    total_hands       = 0

    for _ in range(path_count):
        game      = _make_game(cfg)
        bk        = start_bk
        path      = [bk]
        bet_hist  = [spread_min]        # first snapshot
        tc_hist   = [0.0]               # first snapshot
        running_count = [0]

        # ── patch shoe for Hi-Lo counting ─────────────────────────────────
        if mode in ("hilo", "ap_cover"):
            orig_reset = game.shoe.reset
            orig_draw  = game._draw

            def counting_reset(orig=orig_reset):
                running_count[0] = 0
                orig()

            def counting_draw(count=1, orig=orig_draw):
                cards = orig(count)
                for card in cards:
                    running_count[0] += high_lo_count(card)
                return cards

            game.shoe.reset = counting_reset
            game._draw      = counting_draw

        # ── main loop ─────────────────────────────────────────────────────
        for r in range(rounds):
            decks_left = game.shoe.cards_left / 52

            # Determine bet for this round
            if mode == "basic":
                bet = 1.0

            elif mode == "gambler":
                # Casual hunch: random spike bet in AP spread range
                if hunch_chance > 0 and random.random() < hunch_chance:
                    bet = random.uniform(spread_min, spread_max)
                else:
                    bet = 1.0

            elif mode == "hilo":
                bet = float(bet_spread(
                    running_count[0], decks_left,
                    spread_min=spread_min, spread_max=spread_max,
                ))

            elif mode == "ap_cover":
                bet = float(bet_spread_with_cover(
                    running_count[0], decks_left,
                    spread_min=spread_min, spread_max=spread_max,
                    cover_pct=cover_pct,
                ))

            bet = min(bet, bk)

            net = game.play_with_strategy(strategy_fn, bet=bet)
            bk  = max(0.0, bk + net)
            total_net   += net
            total_hands += 1

            if (r + 1) % snap_every == 0:
                path.append(round(bk, 2))
                bet_hist.append(round(bet, 4))
                # synthetic true count (0 for non-counting strategies)
                tc = running_count[0] / max(decks_left, 0.5) if mode in ("hilo", "ap_cover") else 0.0
                tc_hist.append(round(tc, 2))

            if bk == 0:
                remaining = (rounds - r - 1) // snap_every
                path.extend([0.0] * remaining)
                bet_hist.extend([spread_min] * remaining)
                tc_hist.extend([0.0] * remaining)
                total_hands += (rounds - r - 1)
                break

        all_paths.append(path)
        bet_histories.append(bet_hist)
        tc_histories.append(tc_hist)
        final_bks.append(bk)

    # ── aggregate stats ──────────────────────────────────────────────────────
    final_bks_sorted = sorted(final_bks)
    ruined           = sum(1 for v in final_bks if v == 0)
    median_bk        = final_bks_sorted[len(final_bks_sorted) // 2]
    ev_per_round     = total_net / max(total_hands, 1)
    house_edge_pct   = -ev_per_round * 100

    thresholds = list(range(0, int(start_bk) + 1, max(1, int(start_bk) // 20)))
    ror_curve  = [
        {"threshold": t,
         "pct": round(sum(1 for v in final_bks if v <= t) / path_count * 100, 2)}
        for t in thresholds
    ]

    min_bk    = min(final_bks)
    max_bk    = max(final_bks) if max(final_bks) > min_bk else min_bk + 1
    bin_width = (max_bk - min_bk) / 30
    bins      = [0] * 30
    dist_lbls = [round(min_bk + i * bin_width) for i in range(30)]
    for v in final_bks:
        bins[min(29, int((v - min_bk) / bin_width))] += 1

    # Return only a subset of paths to keep payload size manageable;
    # the casino floor uses up to 50 paths per strategy type.
    MAX_FLOOR_PATHS = 50
    return {
        "paths":          all_paths,
        "bet_histories":  bet_histories[:MAX_FLOOR_PATHS],
        "tc_histories":   tc_histories[:MAX_FLOOR_PATHS],
        "final_bks":      final_bks,
        "median_bk":      round(median_bk, 2),
        "ev_per_round":   round(ev_per_round, 6),
        "house_edge_pct": round(house_edge_pct, 4),
        "ror":            round(ruined / path_count * 100, 2),
        "ror_curve":      ror_curve,
        "dist_labels":    dist_lbls,
        "dist_counts":    bins,
        "start_bk":       start_bk,
        "rounds":         rounds,
        "spread_min":     spread_min,
        "spread_max":     spread_max,
    }


# ── routes ─────────────────────────────────────────────────────────────────────

@app.route("/simulate", methods=["POST"])
def simulate():
    cfg = request.get_json(force=True)
    try:
        # "gambler" mode carries the hunch_chance for casual hunch betting
        gambler_cfg = dict(cfg, hunch_chance=float(cfg.get("hunch_chance", 0.0)))

        # "ap_cover" mode carries the cover_pct deviation
        ap_cover_cfg = dict(cfg, cover_pct=float(cfg.get("cover_pct", 0.0)))

        return jsonify({
            "basic":    _run_paths(cfg, mode="basic"),
            "hilo":     _run_paths(cfg, mode="hilo"),
            "gambler":  _run_paths(gambler_cfg, mode="gambler"),
            "ap_cover": _run_paths(ap_cover_cfg, mode="ap_cover"),
        })
    except Exception as exc:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("=" * 55)
    print("  Blackjack Simulation API  →  http://localhost:5000")
    print("=" * 55)
    app.run(debug=False, port=5000)