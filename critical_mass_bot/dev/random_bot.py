import random


def get_move(state, player_id):
    rows = len(state)
    cols = len(state[0])
    valid_moves = []
    for r in range(rows):
        for c in range(cols):
            owner, _count = state[r][c]
            if owner is None or owner == player_id:
                valid_moves.append((r, c))
    if not valid_moves:
        return (0, 0)
    return random.choice(valid_moves)
