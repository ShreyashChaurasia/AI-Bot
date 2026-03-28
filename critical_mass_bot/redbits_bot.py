import numpy as np
import time
from collections import deque

ROWS = 12
COLS = 8
TOTAL_CELLS = ROWS * COLS
TIME_LIMIT = 0.85
MAX_SEARCH_DEPTH = 30

CAPACITY = np.zeros((ROWS, COLS), dtype=np.int8)
NEIGHBORS = [[[] for _ in range(COLS)] for _ in range(ROWS)]

for _r in range(ROWS):
    for _c in range(COLS):
        is_top = _r == 0
        is_bottom = _r == ROWS - 1
        is_left = _c == 0
        is_right = _c == COLS - 1
        if (is_top and is_left) or (is_top and is_right) or \
           (is_bottom and is_left) or (is_bottom and is_right):
            CAPACITY[_r][_c] = 2
        elif is_top or is_bottom or is_left or is_right:
            CAPACITY[_r][_c] = 3
        else:
            CAPACITY[_r][_c] = 4

        nbrs = []
        if _r - 1 >= 0:
            nbrs.append((_r - 1, _c))
        if _r + 1 < ROWS:
            nbrs.append((_r + 1, _c))
        if _c - 1 >= 0:
            nbrs.append((_r, _c - 1))
        if _c + 1 < COLS:
            nbrs.append((_r, _c + 1))
        NEIGHBORS[_r][_c] = nbrs

CORNER_EDGE_BONUS = np.zeros((ROWS, COLS), dtype=np.float32)
for _r in range(ROWS):
    for _c in range(COLS):
        cap = CAPACITY[_r][_c]
        if cap == 2:
            CORNER_EDGE_BONUS[_r][_c] = 3.0
        elif cap == 3:
            CORNER_EDGE_BONUS[_r][_c] = 1.5

INF = 1e9


def state_to_grids(state):
    owner_grid = np.full((ROWS, COLS), -1, dtype=np.int8)
    count_grid = np.zeros((ROWS, COLS), dtype=np.int8)
    for row in range(ROWS):
        for col in range(COLS):
            owner, orb_count = state[row][col]
            if owner is not None:
                owner_grid[row][col] = owner
                count_grid[row][col] = orb_count
    return owner_grid, count_grid


def count_cells_per_player(owner_grid, count_grid):
    cells_0 = 0
    cells_1 = 0
    for row in range(ROWS):
        for col in range(COLS):
            if count_grid[row][col] > 0:
                if owner_grid[row][col] == 0:
                    cells_0 += 1
                elif owner_grid[row][col] == 1:
                    cells_1 += 1
    return cells_0, cells_1


def simulate(owner_grid, count_grid, player_id, move):
    new_owner = owner_grid.copy()
    new_count = count_grid.copy()

    row, col = move
    new_owner[row][col] = player_id
    new_count[row][col] += 1

    queue = deque()
    if new_count[row][col] >= CAPACITY[row][col]:
        queue.append((row, col))

    iterations = 0
    max_iterations = 500

    while queue and iterations < max_iterations:
        iterations += 1
        curr_row, curr_col = queue.popleft()
        current_count = new_count[curr_row][curr_col]
        cap = CAPACITY[curr_row][curr_col]

        if current_count < cap:
            continue

        exploding_owner = new_owner[curr_row][curr_col]

        cells_0, cells_1 = count_cells_per_player(new_owner, new_count)
        if cells_0 > 0 and cells_1 > 0:
            pass
        elif cells_0 == 0 and cells_1 > 0:
            return new_owner, new_count, 1
        elif cells_1 == 0 and cells_0 > 0:
            return new_owner, new_count, 0

        remaining = current_count - cap
        if remaining > 0:
            new_count[curr_row][curr_col] = remaining
            new_owner[curr_row][curr_col] = exploding_owner
            if remaining >= cap:
                queue.append((curr_row, curr_col))
        else:
            new_count[curr_row][curr_col] = 0
            new_owner[curr_row][curr_col] = -1

        for nbr_row, nbr_col in NEIGHBORS[curr_row][curr_col]:
            new_owner[nbr_row][nbr_col] = exploding_owner
            new_count[nbr_row][nbr_col] += 1
            if new_count[nbr_row][nbr_col] >= CAPACITY[nbr_row][nbr_col]:
                queue.append((nbr_row, nbr_col))

    winner = None
    cells_0, cells_1 = count_cells_per_player(new_owner, new_count)
    if cells_0 == 0 and cells_1 > 0:
        winner = 1
    elif cells_1 == 0 and cells_0 > 0:
        winner = 0

    return new_owner, new_count, winner


def evaluate(owner_grid, count_grid, player_id, moves_played_0, moves_played_1):
    opponent = 1 - player_id

    my_cells = 0
    opp_cells = 0
    my_orbs = 0
    opp_orbs = 0
    my_critical = 0
    opp_critical = 0
    my_corner_edge = 0.0
    opp_corner_edge = 0.0
    explosion_risk = 0

    for row in range(ROWS):
        for col in range(COLS):
            orbs = count_grid[row][col]
            if orbs == 0:
                continue
            owner = owner_grid[row][col]
            cap = CAPACITY[row][col]

            if owner == player_id:
                my_cells += 1
                my_orbs += orbs
                if orbs == cap - 1:
                    my_critical += 1
                my_corner_edge += CORNER_EDGE_BONUS[row][col]
            elif owner == opponent:
                opp_cells += 1
                opp_orbs += orbs
                if orbs == cap - 1:
                    opp_critical += 1
                    for nbr_row, nbr_col in NEIGHBORS[row][col]:
                        if count_grid[nbr_row][nbr_col] > 0 and owner_grid[nbr_row][nbr_col] == player_id:
                            explosion_risk += 1
                opp_corner_edge += CORNER_EDGE_BONUS[row][col]

    both_moved = moves_played_0 > 0 and moves_played_1 > 0
    if both_moved:
        if my_cells == 0:
            return -INF
        if opp_cells == 0:
            return INF

    cell_diff = my_cells - opp_cells
    orb_diff = my_orbs - opp_orbs
    critical_score = my_critical * 3.0 - opp_critical * 3.0
    corner_edge_score = my_corner_edge - opp_corner_edge
    risk_penalty = -explosion_risk * 2.0

    score = (
        cell_diff * 5.0
        + orb_diff * 1.0
        + critical_score
        + corner_edge_score
        + risk_penalty
    )

    return score


def get_valid_moves(owner_grid, count_grid, player_id):
    moves = []
    for row in range(ROWS):
        for col in range(COLS):
            if count_grid[row][col] == 0 or owner_grid[row][col] == player_id:
                moves.append((row, col))
    return moves


def order_moves(owner_grid, count_grid, player_id, moves):
    opponent = 1 - player_id
    priority_0_instant_win = []
    priority_1_explode_opponent = []
    priority_2_near_critical = []
    priority_3_other = []

    for move in moves:
        row, col = move
        orbs = count_grid[row][col]
        cap = CAPACITY[row][col]
        owner = owner_grid[row][col]

        will_explode = (orbs + 1) >= cap

        if will_explode:
            has_opponent_neighbor = False
            triggers_opponent_critical = False
            for nbr_row, nbr_col in NEIGHBORS[row][col]:
                if owner_grid[nbr_row][nbr_col] == opponent and count_grid[nbr_row][nbr_col] > 0:
                    has_opponent_neighbor = True
                    break

            if has_opponent_neighbor:
                priority_1_explode_opponent.append(move)
                continue

        if owner == player_id and orbs == cap - 1:
            priority_2_near_critical.append(move)
            continue

        priority_3_other.append(move)

    return priority_1_explode_opponent + priority_2_near_critical + priority_3_other


def alpha_beta(owner_grid, count_grid, player_id, depth, alpha, beta,
               maximizing, deadline, moves_played_0, moves_played_1):
    if time.time() >= deadline:
        return evaluate(owner_grid, count_grid, player_id, moves_played_0, moves_played_1), None

    current_player = player_id if maximizing else (1 - player_id)
    valid_moves = get_valid_moves(owner_grid, count_grid, current_player)

    if not valid_moves:
        return evaluate(owner_grid, count_grid, player_id, moves_played_0, moves_played_1), None

    if depth == 0:
        return evaluate(owner_grid, count_grid, player_id, moves_played_0, moves_played_1), None

    ordered_moves = order_moves(owner_grid, count_grid, current_player, valid_moves)

    best_move = ordered_moves[0]

    if maximizing:
        max_eval = -INF - 1
        for move in ordered_moves:
            if time.time() >= deadline:
                break

            new_owner, new_count, winner = simulate(owner_grid, count_grid, current_player, move)

            new_mp0 = moves_played_0 + (1 if current_player == 0 else 0)
            new_mp1 = moves_played_1 + (1 if current_player == 1 else 0)

            if winner is not None:
                if winner == player_id:
                    return INF, move
                else:
                    continue

            eval_score, _ = alpha_beta(
                new_owner, new_count, player_id, depth - 1,
                alpha, beta, False, deadline, new_mp0, new_mp1
            )

            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move

            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break

        return max_eval, best_move
    else:
        min_eval = INF + 1
        for move in ordered_moves:
            if time.time() >= deadline:
                break

            new_owner, new_count, winner = simulate(owner_grid, count_grid, current_player, move)

            new_mp0 = moves_played_0 + (1 if current_player == 0 else 0)
            new_mp1 = moves_played_1 + (1 if current_player == 1 else 0)

            if winner is not None:
                if winner == player_id:
                    continue
                else:
                    return -INF, move

            eval_score, _ = alpha_beta(
                new_owner, new_count, player_id, depth - 1,
                alpha, beta, True, deadline, new_mp0, new_mp1
            )

            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move

            beta = min(beta, eval_score)
            if beta <= alpha:
                break

        return min_eval, best_move


def iterative_deepening(owner_grid, count_grid, player_id, deadline, moves_played_0, moves_played_1):
    valid_moves = get_valid_moves(owner_grid, count_grid, player_id)

    if not valid_moves:
        return (0, 0)

    if len(valid_moves) == 1:
        return valid_moves[0]

    ordered = order_moves(owner_grid, count_grid, player_id, valid_moves)
    best_move = ordered[0]

    for depth in range(1, MAX_SEARCH_DEPTH + 1):
        if time.time() >= deadline:
            break

        eval_score, move = alpha_beta(
            owner_grid, count_grid, player_id, depth,
            -INF - 1, INF + 1, True, deadline,
            moves_played_0, moves_played_1
        )

        if move is not None:
            best_move = move

        if eval_score >= INF:
            break

        if time.time() >= deadline:
            break

    return best_move


def estimate_moves_played(owner_grid, count_grid):
    total_orbs = 0
    for row in range(ROWS):
        for col in range(COLS):
            total_orbs += int(count_grid[row][col])

    has_p0 = False
    has_p1 = False
    for row in range(ROWS):
        for col in range(COLS):
            if count_grid[row][col] > 0:
                if owner_grid[row][col] == 0:
                    has_p0 = True
                elif owner_grid[row][col] == 1:
                    has_p1 = True

    mp0 = max(1, total_orbs // 2) if has_p0 else 0
    mp1 = max(1, total_orbs // 2) if has_p1 else 0

    if total_orbs <= 1:
        if has_p0 and not has_p1:
            mp0 = 1
            mp1 = 0
        elif has_p1 and not has_p0:
            mp0 = 0
            mp1 = 1
        elif not has_p0 and not has_p1:
            mp0 = 0
            mp1 = 0

    return mp0, mp1


def get_move(state, player_id):
    start_time = time.time()
    deadline = start_time + TIME_LIMIT

    owner_grid, count_grid = state_to_grids(state)
    moves_played_0, moves_played_1 = estimate_moves_played(owner_grid, count_grid)

    best_move = iterative_deepening(
        owner_grid, count_grid, player_id, deadline,
        moves_played_0, moves_played_1
    )

    return best_move


if __name__ == "__main__":
    test_state = [[(None, 0) for _ in range(COLS)] for _ in range(ROWS)]
    move = get_move(test_state, 0)
    print(f"Bot returned move: {move}")
