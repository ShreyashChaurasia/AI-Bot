import sys
import os
import time
import importlib
import importlib.util

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chain_reaction import ChainReactionGame


def run_match(bot_a_module, bot_b_module, verbose=False):
    game = ChainReactionGame()
    bots = {0: bot_a_module, 1: bot_b_module}
    current_player = 0
    turn_count = 0
    max_turns = 500

    while turn_count < max_turns:
        state = game.get_state()
        bot = bots[current_player]

        start_time = time.time()
        move = bot.get_move(state, current_player)
        elapsed = time.time() - start_time

        if verbose:
            print(f"Turn {turn_count}: Player {current_player} plays {move} ({elapsed:.3f}s)")

        if elapsed > 1.0:
            if verbose:
                print(f"Player {current_player} exceeded time limit!")
            return 1 - current_player

        try:
            game.apply_move(current_player, move)
        except ValueError as exc:
            if verbose:
                print(f"Player {current_player} made invalid move: {exc}")
            return 1 - current_player

        winner = game.check_winner()
        if winner is not None:
            return winner

        current_player = 1 - current_player
        turn_count += 1

    if verbose:
        print("Game reached max turns - draw")
    return -1


def evaluate(bot_a_path, bot_b_path, num_games=10, verbose=False):
    spec_a = importlib.util.spec_from_file_location("bot_a", bot_a_path)
    bot_a = importlib.util.module_from_spec(spec_a)
    spec_a.loader.exec_module(bot_a)

    spec_b = importlib.util.spec_from_file_location("bot_b", bot_b_path)
    bot_b = importlib.util.module_from_spec(spec_b)
    spec_b.loader.exec_module(bot_b)

    wins = {0: 0, 1: 0, -1: 0}

    for game_idx in range(num_games):
        if game_idx % 2 == 0:
            winner = run_match(bot_a, bot_b, verbose=verbose)
            if winner == 0:
                wins[0] += 1
            elif winner == 1:
                wins[1] += 1
            else:
                wins[-1] += 1
            label = f"A=P0 vs B=P1"
        else:
            winner = run_match(bot_b, bot_a, verbose=verbose)
            if winner == 1:
                wins[0] += 1
            elif winner == 0:
                wins[1] += 1
            else:
                wins[-1] += 1
            label = f"A=P1 vs B=P0"

        print(f"Game {game_idx + 1}/{num_games} ({label}): Winner = {'A' if (game_idx % 2 == 0 and winner == 0) or (game_idx % 2 == 1 and winner == 1) else 'B' if winner != -1 else 'Draw'}")

    print(f"\nResults over {num_games} games:")
    print(f"  Bot A wins: {wins[0]}")
    print(f"  Bot B wins: {wins[1]}")
    print(f"  Draws:      {wins[-1]}")
    return wins


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(__file__))
    bot_a_path = os.path.join(base_dir, "redbits_bot.py")
    bot_b_path = os.path.join(os.path.dirname(__file__), "random_bot.py")

    if len(sys.argv) >= 3:
        bot_a_path = sys.argv[1]
        bot_b_path = sys.argv[2]

    num_games = int(sys.argv[3]) if len(sys.argv) >= 4 else 10
    evaluate(bot_a_path, bot_b_path, num_games=num_games, verbose=True)
