from collections import deque
import time

ROWS = 12
COLS = 8
N_CELLS = ROWS * COLS
BASE_TIME_LIMIT = 0.18
MAX_DEPTH = 12
WIN_SCORE = 10_000_000.0

CAPACITY = [0] * N_CELLS
NEIGHBORS = [[] for _ in range(N_CELLS)]
POSITION_WEIGHT = [0.0] * N_CELLS

for r in range(ROWS):
    for c in range(COLS):
        idx = r * COLS + c

        is_top = r == 0
        is_bottom = r == ROWS - 1
        is_left = c == 0
        is_right = c == COLS - 1

        if (is_top and is_left) or (is_top and is_right) or (is_bottom and is_left) or (is_bottom and is_right):
            cap = 2
            pos_w = 2.6
        elif is_top or is_bottom or is_left or is_right:
            cap = 3
            pos_w = 1.3
        else:
            cap = 4
            pos_w = 0.2

        CAPACITY[idx] = cap
        POSITION_WEIGHT[idx] = pos_w

        nbrs = []
        if r > 0:
            nbrs.append((r - 1) * COLS + c)
        if r < ROWS - 1:
            nbrs.append((r + 1) * COLS + c)
        if c > 0:
            nbrs.append(r * COLS + (c - 1))
        if c < COLS - 1:
            nbrs.append(r * COLS + (c + 1))
        NEIGHBORS[idx] = nbrs


def move_to_idx(move):
    return move[0] * COLS + move[1]


def idx_to_move(idx):
    return (idx // COLS, idx % COLS)


def state_to_arrays(state):
    owners = [-1] * N_CELLS
    counts = [0] * N_CELLS
    total_orbs = 0

    idx = 0
    for r in range(ROWS):
        row = state[r]
        for c in range(COLS):
            owner, orb_count = row[c]
            if owner is not None and orb_count > 0:
                owners[idx] = owner
                counts[idx] = int(orb_count)
                total_orbs += int(orb_count)
            idx += 1

    return owners, counts, total_orbs


def count_cells(owners, counts):
    cells_0 = 0
    cells_1 = 0
    for idx in range(N_CELLS):
        if counts[idx] == 0:
            continue
        if owners[idx] == 0:
            cells_0 += 1
        elif owners[idx] == 1:
            cells_1 += 1
    return cells_0, cells_1


def valid_moves(owners, counts, player_id):
    moves = []
    for idx in range(N_CELLS):
        if counts[idx] == 0 or owners[idx] == player_id:
            moves.append(idx)
    return moves


def simulate(owners, counts, player_id, move_idx):
    new_owners = owners[:]
    new_counts = counts[:]

    new_owners[move_idx] = player_id
    new_counts[move_idx] += 1

    queue = deque()
    if new_counts[move_idx] >= CAPACITY[move_idx]:
        queue.append(move_idx)

    while queue:
        cell = queue.popleft()
        cap = CAPACITY[cell]
        if new_counts[cell] < cap:
            continue

        exploding_owner = new_owners[cell]
        new_counts[cell] -= cap

        if new_counts[cell] == 0:
            new_owners[cell] = -1
        else:
            new_owners[cell] = exploding_owner
            if new_counts[cell] >= cap:
                queue.append(cell)

        for nbr in NEIGHBORS[cell]:
            new_owners[nbr] = exploding_owner
            new_counts[nbr] += 1
            if new_counts[nbr] >= CAPACITY[nbr]:
                queue.append(nbr)

    return new_owners, new_counts


def evaluate(owners, counts, root_player, total_orbs):
    opp = 1 - root_player

    my_cells = 0
    opp_cells = 0
    my_orbs = 0
    opp_orbs = 0
    my_pressure = 0
    opp_pressure = 0
    my_positional = 0.0
    opp_positional = 0.0

    my_critical = []
    opp_critical = []

    for idx in range(N_CELLS):
        orb_count = counts[idx]
        if orb_count == 0:
            continue

        owner = owners[idx]
        cap = CAPACITY[idx]
        is_critical = orb_count == (cap - 1)

        if owner == root_player:
            my_cells += 1
            my_orbs += orb_count
            my_positional += POSITION_WEIGHT[idx]
            if is_critical:
                my_pressure += 1
                my_critical.append(idx)
        elif owner == opp:
            opp_cells += 1
            opp_orbs += orb_count
            opp_positional += POSITION_WEIGHT[idx]
            if is_critical:
                opp_pressure += 1
                opp_critical.append(idx)

    if total_orbs >= 2:
        if opp_cells == 0 and my_cells > 0:
            return WIN_SCORE
        if my_cells == 0 and opp_cells > 0:
            return -WIN_SCORE

    my_vulnerability = 0
    for idx in my_critical:
        for nbr in NEIGHBORS[idx]:
            if owners[nbr] == opp and counts[nbr] >= CAPACITY[nbr] - 1:
                my_vulnerability += 1
                break

    opp_vulnerability = 0
    for idx in opp_critical:
        for nbr in NEIGHBORS[idx]:
            if owners[nbr] == root_player and counts[nbr] >= CAPACITY[nbr] - 1:
                opp_vulnerability += 1
                break

    my_moves = 0
    opp_moves = 0
    for idx in range(N_CELLS):
        if counts[idx] == 0:
            my_moves += 1
            opp_moves += 1
        elif owners[idx] == root_player:
            my_moves += 1
        elif owners[idx] == opp:
            opp_moves += 1

    score = 0.0
    score += (my_cells - opp_cells) * 14.0
    score += (my_orbs - opp_orbs) * 2.6
    score += (my_pressure - opp_pressure) * 5.0
    score += (my_positional - opp_positional) * 2.2
    score += (opp_vulnerability - my_vulnerability) * 7.5
    score += (my_moves - opp_moves) * 0.35

    return score


def move_priority(owners, counts, player_id, move_idx):
    opp = 1 - player_id
    cap = CAPACITY[move_idx]
    current = counts[move_idx]
    owner = owners[move_idx]

    score = POSITION_WEIGHT[move_idx] * 2.0

    if current + 1 >= cap:
        score += 20.0
        for nbr in NEIGHBORS[move_idx]:
            if counts[nbr] == 0:
                continue
            if owners[nbr] == opp:
                score += 9.0
                if counts[nbr] >= CAPACITY[nbr] - 1:
                    score += 8.0
            elif owners[nbr] == player_id and counts[nbr] >= CAPACITY[nbr] - 1:
                score += 2.5
    else:
        if owner == player_id and current == cap - 1:
            score += 8.0

    for nbr in NEIGHBORS[move_idx]:
        if owners[nbr] == opp and counts[nbr] >= CAPACITY[nbr] - 1:
            score -= 4.0

    return score


def order_moves(owners, counts, player_id, moves):
    scored = []
    for move in moves:
        scored.append((move_priority(owners, counts, player_id, move), move))
    scored.sort(reverse=True)
    return [move for _score, move in scored]


def terminal_score_if_any(owners, counts, root_player, total_orbs):
    if total_orbs < 2:
        return None

    cells_0, cells_1 = count_cells(owners, counts)
    if cells_0 > 0 and cells_1 > 0:
        return None

    if root_player == 0:
        if cells_1 == 0 and cells_0 > 0:
            return WIN_SCORE
        if cells_0 == 0 and cells_1 > 0:
            return -WIN_SCORE
    else:
        if cells_0 == 0 and cells_1 > 0:
            return WIN_SCORE
        if cells_1 == 0 and cells_0 > 0:
            return -WIN_SCORE

    return None


def negamax(owners, counts, current_player, root_player, depth, alpha, beta, deadline, total_orbs):
    if time.perf_counter() >= deadline:
        return evaluate(owners, counts, root_player, total_orbs), None, True

    terminal_score = terminal_score_if_any(owners, counts, root_player, total_orbs)
    if terminal_score is not None:
        return terminal_score, None, False

    if depth == 0:
        return evaluate(owners, counts, root_player, total_orbs), None, False

    moves = valid_moves(owners, counts, current_player)
    if not moves:
        # No legal move means this branch is effectively lost after opening turns.
        if total_orbs >= 2:
            if current_player == root_player:
                return -WIN_SCORE + 1.0, None, False
            return WIN_SCORE - 1.0, None, False
        return evaluate(owners, counts, root_player, total_orbs), None, False

    ordered_moves = order_moves(owners, counts, current_player, moves)

    best_move = ordered_moves[0]
    best_score = -WIN_SCORE * 10.0

    for move in ordered_moves:
        if time.perf_counter() >= deadline:
            if best_score <= -WIN_SCORE * 9.0:
                return evaluate(owners, counts, root_player, total_orbs), best_move, True
            return best_score, best_move, True

        child_owners, child_counts = simulate(owners, counts, current_player, move)
        child_score, _child_move, timed_out = negamax(
            child_owners,
            child_counts,
            1 - current_player,
            root_player,
            depth - 1,
            -beta,
            -alpha,
            deadline,
            total_orbs + 1,
        )

        if timed_out:
            if best_score <= -WIN_SCORE * 9.0:
                return evaluate(owners, counts, root_player, total_orbs), best_move, True
            return best_score, best_move, True

        score = -child_score
        if score > best_score:
            best_score = score
            best_move = move

        if score > alpha:
            alpha = score

        if alpha >= beta:
            break

    return best_score, best_move, False


def choose_move(owners, counts, player_id, total_orbs, deadline):
    moves = valid_moves(owners, counts, player_id)
    if not moves:
        return 0
    if len(moves) == 1:
        return moves[0]

    ordered = order_moves(owners, counts, player_id, moves)
    best_move = ordered[0]

    # Quick tactical finish detection before deep search.
    if total_orbs + 1 >= 2:
        for move in ordered:
            child_owners, child_counts = simulate(owners, counts, player_id, move)
            cells_0, cells_1 = count_cells(child_owners, child_counts)
            if player_id == 0 and cells_1 == 0 and cells_0 > 0:
                return move
            if player_id == 1 and cells_0 == 0 and cells_1 > 0:
                return move

    depth = 1
    while depth <= MAX_DEPTH and time.perf_counter() < deadline:
        score, move, timed_out = negamax(
            owners,
            counts,
            player_id,
            player_id,
            depth,
            -WIN_SCORE * 10.0,
            WIN_SCORE * 10.0,
            deadline,
            total_orbs,
        )

        if timed_out:
            break

        if move is not None:
            best_move = move

        if score >= WIN_SCORE - 1.0:
            break

        depth += 1

    return best_move


def compute_time_budget(total_orbs, legal_move_count):
    if total_orbs < 8:
        budget = 0.08
    elif total_orbs < 40:
        budget = 0.14
    else:
        budget = BASE_TIME_LIMIT

    if legal_move_count > 50:
        budget -= 0.03
    elif legal_move_count < 20:
        budget += 0.03

    if budget < 0.05:
        return 0.05
    if budget > 0.24:
        return 0.24
    return budget


def get_move(state, player_id):
    owners, counts, total_orbs = state_to_arrays(state)

    legal = valid_moves(owners, counts, player_id)
    if not legal:
        return (0, 0)

    # Opening corner preference gives stable early control at near-zero cost.
    if total_orbs == 0:
        return (ROWS - 1, COLS - 1)

    budget = compute_time_budget(total_orbs, len(legal))
    deadline = time.perf_counter() + budget

    best_idx = choose_move(owners, counts, player_id, total_orbs, deadline)
    return idx_to_move(best_idx)


if __name__ == "__main__":
    empty_state = [[(None, 0) for _ in range(COLS)] for _ in range(ROWS)]
    print(get_move(empty_state, 0))
