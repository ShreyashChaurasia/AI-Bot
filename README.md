# AI-Bot

Chain Reaction bot for the CRITICAL MASS AI competition (NJACK, IIT Patna).

## Project Layout

- `critical_mass_bot/chain_reaction.py`: Local game engine used for testing and evaluation.
- `critical_mass_bot/dev/evaluate.py`: Match runner for bot-vs-bot evaluation.
- `critical_mass_bot/dev/random_bot.py`: Baseline random bot.
- `critical_mass_bot/dev/dummy_bot.py`: Baseline deterministic bot.
- `critical_mass_bot/redbits_bot.py`: Main competitive bot implementation.
- `critical_mass_bot/teamname_bot.py`: Submission-ready script file name required by the competition.

## Bot Strategy (redbits/teamname bot)

The bot uses iterative deepening minimax with alpha-beta pruning, tuned for the 12x8 Chain Reaction board and 1 second move limit.

### 1) Time-safe search

- Uses an adaptive internal budget (`~0.05s` to `~0.24s` depending on game phase and branching) so each move stays well below the 1 second hard limit.
- Runs depth `1 -> N` (iterative deepening) and always keeps the best fully-searched move from the latest completed depth.
- Stops immediately when the deadline is reached and returns the last safe result.

### 2) Fast chain reaction simulation

- Board is converted from `(owner, orb_count)` tuples into compact arrays for speed.
- Move simulation uses a queue-based explosion propagation model.
- Captures and recursive reactions are handled exactly according to critical mass rules.

### 3) Move ordering for stronger pruning

Candidate moves are sorted by tactical priority before search:

- Moves that explode immediately.
- Explosions that hit opponent clusters or opponent near-critical cells.
- Stable corner/edge occupation.
- Penalties for walking into obvious counter-explosion danger.

Better ordering improves alpha-beta pruning and lets the bot search deeper within the same time budget.

### 4) Evaluation function (non-hardcoded, dynamic)

The bot scores states using a weighted blend of dynamic features:

- Cell control difference.
- Orb count difference.
- Near-critical pressure (offensive potential).
- Positional stability (corner/edge preference).
- Vulnerability analysis (critical cells exposed to enemy chain triggers).
- Mobility difference (legal options for both players).

It also detects terminal elimination states once both players have had turns.

### 5) Tactical instant-win check

Before deep search, the bot quickly scans for immediate winning moves and takes them instantly.

## Competition Compliance

- Language: Python.
- No extra threads used.
- Valid move always returned (no forfeits).
- Per-move compute kept under competition threshold.
- Uses only standard Python library.

## How to Run Local Evaluation

From repo root:

```powershell
python critical_mass_bot/dev/evaluate.py
```

Custom bots and game count:

```powershell
python critical_mass_bot/dev/evaluate.py critical_mass_bot/redbits_bot.py critical_mass_bot/dev/random_bot.py 20
```

Test submission filename directly:

```powershell
python critical_mass_bot/dev/evaluate.py critical_mass_bot/teamname_bot.py critical_mass_bot/dev/random_bot.py 20
```

## Submission Notes

For final competition submission, upload:

1. `teamname_bot.py` (single script).
2. A short PDF/TXT strategy summary (you can reuse the Bot Strategy section from this README).
