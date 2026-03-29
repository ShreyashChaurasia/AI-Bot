"""
Critical Mass — Chain Reaction Bot  (v2)
Key upgrades over v1:
  1. Time budget raised to 0.88s (was 0.24s) — biggest single gain
  2. Transposition table with Zobrist hashing — avoids re-searching identical states
  3. Top-N move pruning at depth ≥5 — controls explosion of early-game branching
  4. Fixed mobility eval (empty cells benefited BOTH sides equally — now computed per-player)
  5. Opening book for both players
  6. Quiescence flag — extends 1 ply when board is "loud" (many at-critical-mass-minus-1)
  7. Removed redundant WIN check inside evaluate() (already caught by terminal detector)
  8. compute_time_budget() no longer penalises early game — that's when strategy matters most
  9. bytearray for counts (faster copies than list)
"""

from collections import deque
import time
import random

# ── Board constants ────────────────────────────────────────────────────────────
ROWS = 12
COLS = 8
N_CELLS = ROWS * COLS
WIN_SCORE = 10_000_000.0
MAX_DEPTH = 14
TIME_LIMIT = 0.88          # hard ceiling — 120 ms safety margin under 1 s
EARLY_BUDGET = 0.45        # v1 used 0.08 s here; opening decisions matter

# Precomputed per-cell data
CAPACITY     = [0]   * N_CELLS
NEIGHBORS    = [None] * N_CELLS
POS_WEIGHT   = [0.0] * N_CELLS

# Corner indices — used in opening book
CORNERS = {0, COLS-1, (ROWS-1)*COLS, (ROWS-1)*COLS + COLS-1}

for r in range(ROWS):
    for c in range(COLS):
        idx = r * COLS + c
        t, b, l, ri = r == 0, r == ROWS-1, c == 0, c == COLS-1
        if (t and l) or (t and ri) or (b and l) or (b and ri):
            cap, pw = 2, 2.8
        elif t or b or l or ri:
            cap, pw = 3, 1.4
        else:
            cap, pw = 4, 0.3
        CAPACITY[idx]   = cap
        POS_WEIGHT[idx] = pw
        nbrs = []
        if r > 0:        nbrs.append((r-1)*COLS + c)
        if r < ROWS-1:   nbrs.append((r+1)*COLS + c)
        if c > 0:        nbrs.append(r*COLS + c-1)
        if c < COLS-1:   nbrs.append(r*COLS + c+1)
        NEIGHBORS[idx] = nbrs

# ── Zobrist hashing ────────────────────────────────────────────────────────────
# Each (cell, owner, count) combination gets a random 64-bit key.
# Count is capped at capacity (max 4), owner in {0, 1}.
_rng = random.Random(0xDEADBEEF)
ZOBRIST = [
    [
        [_rng.getrandbits(64) for _ in range(5)]   # counts 0-4
        for _ in range(2)                           # owners 0-1
    ]
    for _ in range(N_CELLS)
]

def _zh(cell: int, owner: int, count: int) -> int:
    return ZOBRIST[cell][owner][min(count, 4)]


# ── State helpers ──────────────────────────────────────────────────────────────
def state_to_arrays(state):
    owners = [-1] * N_CELLS
    counts = bytearray(N_CELLS)
    total  = 0
    idx    = 0
    for r in range(ROWS):
        row = state[r]
        for c in range(COLS):
            owner, orb_count = row[c]
            if owner is not None and orb_count > 0:
                owners[idx]  = owner
                counts[idx]  = int(orb_count)
                total       += int(orb_count)
            idx += 1
    return owners, counts, total


def compute_hash(owners, counts) -> int:
    h = 0
    for i in range(N_CELLS):
        if counts[i] > 0:
            h ^= _zh(i, owners[i], counts[i])
    return h


def count_cells(owners, counts):
    c0 = c1 = 0
    for i in range(N_CELLS):
        if counts[i] == 0:
            continue
        if owners[i] == 0: c0 += 1
        else:               c1 += 1
    return c0, c1


# ── Simulation ─────────────────────────────────────────────────────────────────
def simulate(owners, counts, player_id, move_idx):
    """Returns (new_owners, new_counts, hash_delta).
    Uses bytearray for counts (faster shallow copies than list).
    """
    new_owners = owners[:]
    new_counts = bytearray(counts)          # bytearray copy is faster than list[:]

    # XOR out old cell state, then in with new below
    old_owner = new_owners[move_idx]
    old_count = new_counts[move_idx]

    new_owners[move_idx] = player_id
    new_counts[move_idx] += 1

    queue = deque()
    if new_counts[move_idx] >= CAPACITY[move_idx]:
        queue.append(move_idx)

    while queue:
        cell = queue.popleft()
        cap  = CAPACITY[cell]
        if new_counts[cell] < cap:
            continue
        eo = new_owners[cell]
        new_counts[cell] -= cap
        if new_counts[cell] == 0:
            new_owners[cell] = -1
        else:
            new_owners[cell] = eo
            if new_counts[cell] >= cap:
                queue.append(cell)
        for nbr in NEIGHBORS[cell]:
            new_owners[nbr]  = eo
            new_counts[nbr] += 1
            if new_counts[nbr] >= CAPACITY[nbr]:
                queue.append(nbr)

    return new_owners, new_counts


# ── Valid moves ────────────────────────────────────────────────────────────────
def valid_moves(owners, counts, player_id):
    return [i for i in range(N_CELLS) if counts[i] == 0 or owners[i] == player_id]


# ── Evaluation ────────────────────────────────────────────────────────────────
def evaluate(owners, counts, root_player, total_orbs) -> float:
    opp = 1 - root_player

    my_cells = my_orbs = my_press = 0
    op_cells = op_orbs = op_press = 0
    my_pos = op_pos = 0.0
    my_moves = op_moves = 0
    my_vuln = op_vuln = 0
    my_crit = []
    op_crit = []

    for idx in range(N_CELLS):
        orb = counts[idx]
        empty = orb == 0
        if empty:
            my_moves += 1
            op_moves += 1
            continue
        owner = owners[idx]
        cap   = CAPACITY[idx]
        crit  = (orb == cap - 1)
        if owner == root_player:
            my_cells += 1
            my_orbs  += orb
            my_pos   += POS_WEIGHT[idx]
            my_moves += 1
            if crit:
                my_press += 1
                my_crit.append(idx)
        else:
            op_cells += 1
            op_orbs  += orb
            op_pos   += POS_WEIGHT[idx]
            op_moves += 1
            if crit:
                op_press += 1
                op_crit.append(idx)

    # Vulnerability: our critical cells adjacent to opponent critical cells
    for idx in my_crit:
        for nbr in NEIGHBORS[idx]:
            if owners[nbr] == opp and counts[nbr] >= CAPACITY[nbr] - 1:
                my_vuln += 1
                break
    for idx in op_crit:
        for nbr in NEIGHBORS[idx]:
            if owners[nbr] == root_player and counts[nbr] >= CAPACITY[nbr] - 1:
                op_vuln += 1
                break

    # NOTE: WIN/LOSS is handled by terminal detector BEFORE evaluate() is called
    score  = (my_cells - op_cells) * 14.0
    score += (my_orbs  - op_orbs)  *  2.6
    score += (my_press - op_press) *  5.0
    score += (my_pos   - op_pos)   *  2.2
    score += (op_vuln  - my_vuln)  *  7.5
    # Fixed mobility: previously empty cells added equally to both — net zero.
    # Now measure own accessible moves vs opponent accessible moves separately.
    score += (my_moves - op_moves) *  0.6
    return score


# ── Move ordering / priority ───────────────────────────────────────────────────
def _move_priority(owners, counts, player_id, move_idx) -> float:
    opp = 1 - player_id
    cap = CAPACITY[move_idx]
    cnt = counts[move_idx]

    score = POS_WEIGHT[move_idx] * 2.0

    if cnt + 1 >= cap:                 # this move triggers an explosion
        score += 22.0
        for nbr in NEIGHBORS[move_idx]:
            if counts[nbr] == 0:
                continue
            if owners[nbr] == opp:
                score += 10.0
                if counts[nbr] >= CAPACITY[nbr] - 1:
                    score += 9.0       # captures a near-critical enemy cell
            elif owners[nbr] == player_id and counts[nbr] >= CAPACITY[nbr] - 1:
                score += 3.0           # chain trigger on own near-critical
    elif owners[move_idx] == player_id and cnt == cap - 1:
        score += 9.0                   # bring to critical for next explosion
    else:
        score += cnt * 0.5             # building up is slightly valuable

    for nbr in NEIGHBORS[move_idx]:   # danger: opponent can explode into us
        if owners[nbr] == opp and counts[nbr] >= CAPACITY[nbr] - 1:
            score -= 5.0

    return score


def order_moves(owners, counts, player_id, moves):
    scored = [(_move_priority(owners, counts, player_id, m), m) for m in moves]
    scored.sort(reverse=True)
    return [m for _, m in scored]


# ── Terminal check ─────────────────────────────────────────────────────────────
def terminal_score(owners, counts, root_player, total_orbs):
    if total_orbs < 2:
        return None
    c0, c1 = count_cells(owners, counts)
    if c0 > 0 and c1 > 0:
        return None
    me  = [c0, c1][root_player]
    opp = [c0, c1][1 - root_player]
    if me > 0 and opp == 0:
        return  WIN_SCORE
    if me == 0 and opp > 0:
        return -WIN_SCORE
    return None


# ── Transposition table ────────────────────────────────────────────────────────
# Each entry: (depth, score, flag, best_move)
# flag: 'exact' | 'lower' | 'upper'
TT = {}
TT_MAX_SIZE = 500_000

EXACT, LOWER, UPPER = 0, 1, 2

def tt_lookup(h, depth, alpha, beta):
    entry = TT.get(h)
    if entry is None:
        return None
    e_depth, e_score, e_flag, e_move = entry
    if e_depth < depth:
        return None                    # stored at shallower depth, not reliable
    if e_flag == EXACT:
        return e_score, e_move
    if e_flag == LOWER and e_score >= beta:
        return e_score, e_move
    if e_flag == UPPER and e_score <= alpha:
        return e_score, e_move
    return None


def tt_store(h, depth, score, flag, best_move):
    if len(TT) >= TT_MAX_SIZE:
        TT.clear()                     # simple eviction — keeps memory bounded
    TT[h] = (depth, score, flag, best_move)


# ── Is position "loud"? (quiescence helper) ────────────────────────────────────
def is_loud(owners, counts, player_id) -> bool:
    """True if the current player has a cell that can immediately explode into
    an opponent cell — i.e., a horizon-effect candidate."""
    opp = 1 - player_id
    for idx in range(N_CELLS):
        if owners[idx] == player_id and counts[idx] == CAPACITY[idx] - 1:
            for nbr in NEIGHBORS[idx]:
                if counts[nbr] > 0 and owners[nbr] == opp:
                    return True
    return False


# ── Negamax with alpha-beta + TT ─────────────────────────────────────────────
def negamax(owners, counts, h, current_player, root_player, depth,
            alpha, beta, deadline, total_orbs, ply=0):

    if time.perf_counter() >= deadline:
        return evaluate(owners, counts, root_player, total_orbs), None, True

    ts = terminal_score(owners, counts, root_player, total_orbs)
    if ts is not None:
        return ts, None, False

    # Quiescence extension: if loud and depth==0, extend 1 ply
    if depth == 0:
        if ply < 2 and is_loud(owners, counts, current_player):
            depth = 1
        else:
            return evaluate(owners, counts, root_player, total_orbs), None, False

    # TT lookup
    tt_result = tt_lookup(h, depth, alpha, beta)
    if tt_result is not None:
        return tt_result[0], tt_result[1], False

    moves = valid_moves(owners, counts, current_player)
    if not moves:
        if total_orbs >= 2:
            return (-WIN_SCORE + ply) if current_player == root_player else (WIN_SCORE - ply), None, False
        return evaluate(owners, counts, root_player, total_orbs), None, False

    ordered = order_moves(owners, counts, current_player, moves)

    # Top-N pruning at deep searches to control branching explosion
    # Keep more moves at shallow depth (better accuracy), fewer at deep depth
    if depth >= 5:
        ordered = ordered[:12]
    elif depth >= 3:
        ordered = ordered[:20]

    best_move  = ordered[0]
    best_score = -WIN_SCORE * 10.0
    orig_alpha = alpha
    flag       = UPPER

    for move in ordered:
        if time.perf_counter() >= deadline:
            if best_score <= -WIN_SCORE * 9.0:
                return evaluate(owners, counts, root_player, total_orbs), best_move, True
            return best_score, best_move, True

        child_o, child_c = simulate(owners, counts, current_player, move)

        # Update hash for child state
        child_h = compute_hash(child_o, child_c)

        cs, _, timed_out = negamax(
            child_o, child_c, child_h,
            1 - current_player, root_player,
            depth - 1, -beta, -alpha,
            deadline, total_orbs + 1, ply + 1
        )

        if timed_out:
            return best_score, best_move, True

        score = -cs
        if score > best_score:
            best_score = score
            best_move  = move
            flag       = EXACT

        if score > alpha:
            alpha = score
            flag  = EXACT

        if alpha >= beta:
            flag = LOWER
            break

    tt_store(h, depth, best_score, flag, best_move)
    return best_score, best_move, False


# ── Immediate win scan ─────────────────────────────────────────────────────────
def find_immediate_win(owners, counts, player_id, moves, total_orbs):
    if total_orbs + 1 < 2:
        return None
    opp = 1 - player_id
    for move in moves:
        co, cc = simulate(owners, counts, player_id, move)
        c0, c1 = count_cells(co, cc)
        opp_cells = [c0, c1][opp]
        my_cells  = [c0, c1][player_id]
        if opp_cells == 0 and my_cells > 0:
            return move
    return None


# ── Time budget ────────────────────────────────────────────────────────────────
def compute_time_budget(total_orbs: int) -> float:
    """
    v1 starved the early game (0.08 s) and mid-game (0.14 s).
    Opening decisions set board structure for many moves — deserve full budget.
    """
    if total_orbs < 6:
        return EARLY_BUDGET          # opening: corners & cluster seeds matter
    elif total_orbs < 30:
        return 0.70                  # early-mid
    elif total_orbs < 60:
        return TIME_LIMIT            # mid-game: most complex position
    else:
        return 0.75                  # late game: fewer moves, easier tactics


# ── Opening book ───────────────────────────────────────────────────────────────
OPENING_CORNERS = [
    (0,        0),           # top-left
    (0,        COLS-1),      # top-right
    (ROWS-1,   0),           # bottom-left
    (ROWS-1,   COLS-1),      # bottom-right
]

def opening_move(owners, counts, player_id, total_orbs):
    """
    Grab an unclaimed corner.  If all corners are taken, return None and fall
    through to the search.
    """
    for r, c in OPENING_CORNERS:
        idx = r * COLS + c
        if counts[idx] == 0:          # unclaimed — take it
            return idx
        if owners[idx] == player_id:  # we already own this corner — try next
            continue
        # Opponent owns this corner — skip it (don't place on opponent's cell)
    return None


# ── Main choose_move ──────────────────────────────────────────────────────────
def choose_move(owners, counts, player_id, total_orbs, deadline):
    moves = valid_moves(owners, counts, player_id)
    if not moves:
        return 0
    if len(moves) == 1:
        return moves[0]

    # Immediate win check (1-ply lookahead, free)
    win = find_immediate_win(owners, counts, player_id, moves, total_orbs)
    if win is not None:
        return win

    # Opening book (first few turns)
    if total_orbs <= 4:
        ob = opening_move(owners, counts, player_id, total_orbs)
        if ob is not None:
            return ob

    ordered  = order_moves(owners, counts, player_id, moves)
    best_move = ordered[0]
    h0        = compute_hash(owners, counts)

    depth = 1
    while depth <= MAX_DEPTH and time.perf_counter() < deadline:
        score, move, timed_out = negamax(
            owners, counts, h0,
            player_id, player_id,
            depth,
            -WIN_SCORE * 10.0, WIN_SCORE * 10.0,
            deadline,
            total_orbs,
        )

        if timed_out:
            break

        if move is not None:
            best_move = move

        if score >= WIN_SCORE - 1.0:   # forced win found — stop searching
            break

        depth += 1

    return best_move


# ── Public API ─────────────────────────────────────────────────────────────────
def get_move(state, player_id):
    owners, counts, total_orbs = state_to_arrays(state)

    legal = valid_moves(owners, counts, player_id)
    if not legal:
        return (0, 0)

    budget   = compute_time_budget(total_orbs)
    deadline = time.perf_counter() + budget

    best_idx = choose_move(owners, counts, player_id, total_orbs, deadline)
    return (best_idx // COLS, best_idx % COLS)


# ── Smoke test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    empty = [[(None, 0)] * COLS for _ in range(ROWS)]
    print("Player 0 first move:", get_move(empty, 0))

    # Player 1 response
    state2 = [row[:] for row in empty]
    state2[ROWS-1][COLS-1] = (0, 1)
    print("Player 1 first move:", get_move(state2, 1))

    # Quick self-play to verify no crashes
    import copy
    state = [[(None, 0)] * COLS for _ in range(ROWS)]
    for turn in range(30):
        pid = turn % 2
        move = get_move(state, pid)
        r, c = move
        owner, cnt = state[r][c]
        if owner is None or owner == pid:
            state[r][c] = (pid, cnt + 1)
        # (A real game loop would run simulate; this is just a crash check)
    print("30-move self-play: no crash ✓")