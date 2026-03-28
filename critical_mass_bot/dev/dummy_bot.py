def get_move(state, player_id):
    rows = len(state)
    cols = len(state[0])
    for r in range(rows):
        for c in range(cols):
            owner, _count = state[r][c]
            if owner is None or owner == player_id:
                return (r, c)
    return (0, 0)
