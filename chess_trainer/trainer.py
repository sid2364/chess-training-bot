#!/usr/bin/env python3
import os

try:  # optional dependency for .env support
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    def load_dotenv() -> None:
        pass

try:  # optional network dependency
    import berserk
except Exception:  # pragma: no cover - optional dependency
    berserk = None

try:  # optional chess engine library
    import chess
    import chess.engine
except Exception:  # pragma: no cover - optional dependency
    chess = None

from .bot_profile import BotProfile

load_dotenv()  # read token from environment if available
API_TOKEN = os.getenv("LICHESS_BOT_TOKEN")

"""Main bot training loop and event handling."""

from . import openings_explorer
STOCKFISH_PATH = "/usr/games/stockfish"
# TODO check if the binary actually exists in this path, if not, do "which stockfish" and use that path instead

OUR_NAME = "chess-trainer-bot" # to identify our name on Lichess
TIME_PER_MOVE = 5
# CHALLENGE = 100 # how much to increase bot ELO compared to player's

if berserk is not None and API_TOKEN:
    session = berserk.TokenSession(API_TOKEN)
    client = berserk.Client(session=session)
else:  # pragma: no cover - allows running tests without optional deps
    session = client = None


############################################### Core Bot Logic ####################################

def handle_events(bot_profile: BotProfile = BotProfile(), on_game_start=None):
    for event in client.bots.stream_incoming_events():
        t = event["type"]
        if t == "challenge":
            client.bots.accept_challenge(event["challenge"]["id"])
            print("Accepted challenge!")
        elif t == "gameStart":
            game_id = event["game"]["id"]
            if on_game_start is not None:
                try:
                    on_game_start(game_id)
                except Exception:
                    pass
            print(f"Game started: {game_id}")
            play_game(game_id, bot_profile)

def make_move_on_board(board, game_id, chosen_move_uci):
    client.bots.make_move(game_id, chosen_move_uci)
    board.push_uci(chosen_move_uci)

def play_game(game_id, bot_profile: BotProfile):
    """
    Main game loop to play
    """
    print("in play_game, bot_profile=", bot_profile)
    # Launch engine
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    stream = client.bots.stream_game_state(game_id)

    # First message contains players’ ratings
    start = next(stream)
    bot_profile.determine_color_and_opp_rating(start)
    # print("our_color, opp_rating", bot_profile.our_color, bot_profile.opp_rating)

    print(f"Playing as {'White' if bot_profile.our_color else 'Black'} vs {bot_profile.opp_rating}-rated opponent")
    bot_profile.opp_rating += bot_profile.challenge
    print(f"BOT will play at ELO: {bot_profile.opp_rating}")

    bot_profile.opp_rating = max(1320, bot_profile.opp_rating)

    # Configure Stockfish to match opponent’s strength
    engine.configure({
        "UCI_LimitStrength": True,
        "UCI_Elo": bot_profile.opp_rating
    })

    init_moves_str = start.get("state", {}).get("moves", "")
    init_moves = init_moves_str.split()
    board = chess.Board()

    print(init_moves)
    if init_moves:
        print("Moves played so far:")
        for idx, uci in enumerate(init_moves, start=1):
            color = "White" if (idx % 2) == 1 else "Black"
            print(f"  {idx}. {color}: {uci}")
            board.push_uci(uci)
    else:
        print("No moves played yet; starting from the initial position.")

    if board.turn == bot_profile.our_color:
        print("It's the BOT's turn!")
        chosen_move_uci = openings_explorer.get_book_move(board, bot_profile)
        if chosen_move_uci is None:
            engine_move = engine.play(board, limit=chess.engine.Limit(time=TIME_PER_MOVE))
            chosen_move_uci = engine_move.move.uci()
            make_move_on_board(board, game_id, chosen_move_uci)
            print(f"-> (first move from engine) {chosen_move_uci}")
        else:
            make_move_on_board(board, game_id, chosen_move_uci)
            print(f"-> (first move from openings database) {chosen_move_uci}")

    else:
        print("It's the player's turn!")

    # Main loop: respond whenever it’s our turn
    for ev in stream:
        # print("ev", ev)
        if ev.get("type") != "gameState":
            continue

        # print("board.turn", board.turn)

        # Rebuild position
        board.reset()
        for uci in ev["moves"].split():
            board.push_uci(uci)

        # Only play when it's our turn
        if board.turn == bot_profile.our_color:
            chosen_move_uci = openings_explorer.get_book_move(board, bot_profile)
            if chosen_move_uci is None:
                engine_move = engine.play(board, limit=chess.engine.Limit(time=TIME_PER_MOVE))
                if engine_move.move is None: # The game is over!
                    print("You won!")
                    break
                chosen_move_uci = engine_move.move.uci()
                make_move_on_board(board, game_id, chosen_move_uci)
                print(f"-> (from engine) {chosen_move_uci}")
            else:
                make_move_on_board(board, game_id, chosen_move_uci)
                print(f"-> (from openings database) {chosen_move_uci}")

    engine.quit()

def main() -> None:
    """Entry point for running the training bot via ``python -m``."""

    profile = BotProfile()

    try:
        profile.get_openings_choice_from_user()
    except KeyboardInterrupt:
        print("Exiting")
        return

    white, black = profile.get_clean_openings()
    print(
        "The bot will play:-\n as White -> {}\n as Black -> {}".format(
            ", ".join(white), ", ".join(black)
        )
    )

    try:
        handle_events(bot_profile=profile)
    except KeyboardInterrupt:
        print("Exiting")


if __name__ == "__main__":
    main()
