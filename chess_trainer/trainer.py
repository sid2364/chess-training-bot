#!/usr/bin/env python3
import os
import sys
import shutil
import threading
from typing import Optional
import webbrowser

from berserk.exceptions import ResponseError

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

def find_stockfish_binary() -> str:
    # Override via .env
    env_path = os.getenv("STOCKFISH_PATH")
    if env_path:
        if os.path.isfile(env_path) and os.access(env_path, os.X_OK):
            return env_path
        else:
            print(f"STOCKFISH_PATH is set to {env_path} but it's not an executable file", file=sys.stderr)

    # Check built‑in default for stockfish on Ubuntu
    default_path = "/usr/games/stockfish"
    if os.path.isfile(default_path) and os.access(default_path, os.X_OK):
        return default_path

    # Fallback to PATH, if all else fails
    which_path = shutil.which("stockfish")
    if which_path:
        return which_path

    # Nothing found, so crash
    raise FileNotFoundError(
        "Could not locate the Stockfish binary! Please install Stockfish or set the STOCKFISH_PATH in .env to the executable!"
    )

from . import lichess_openings_explorer
STOCKFISH_PATH = find_stockfish_binary() # "/usr/games/stockfish"

# OUR_NAME = "chess-trainer-bot" # to identify our name on Lichess
OUR_NAME = os.getenv("LICHESS_BOT_NAME")
TIME_PER_MOVE = 2
# CHALLENGE = 100 # how much to increase bot ELO compared to player's

if berserk is not None and API_TOKEN:
    session = berserk.TokenSession(API_TOKEN)
    client = berserk.Client(session=session)
else:  # pragma: no cover - allows running tests without optional deps
    session = client = None

############################################### Core Bot Logic ####################################

def handle_events(
    bot_profile: BotProfile = BotProfile(),
    on_game_start=None,
    stop_event: Optional[threading.Event] = None,
):
    print("Listening for events now...")
    for event in client.bots.stream_incoming_events():
        if stop_event is not None and stop_event.is_set():
            break
        t = event["type"]
        if t == "challenge":
            try:
                client.bots.accept_challenge(event["challenge"]["id"])
            except ResponseError:
                print("Could not accept challenge! Moving on...")
            print("Accepted challenge!")
        elif t == "gameStart":
            game_id = event["game"]["id"]
            if on_game_start is not None:
                try:
                    on_game_start(game_id)
                except Exception:
                    pass
            print(f"Game started: {game_id}")
            try:
                play_game(game_id, bot_profile)
            except Exception as e:
                print("Game discontinued, moving on to the next one...")

def make_move_on_board(board, game_id, chosen_move_uci):
    try:
        client.bots.make_move(game_id, chosen_move_uci)
    except ResponseError as e:
        print(f"Could not make a move: {e}")
        return
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
    bot_profile.opp_rating = min(3190, bot_profile.opp_rating)

    # Configure Stockfish to match opponent’s strength
    engine.configure({
        "UCI_LimitStrength": True,
        "UCI_Elo": bot_profile.opp_rating,
        #"Ponder": True, # think while opponent is thinking, apparently automatically managed!
        "Threads": 4
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

    # open the browser at https://lichess.org/@/chess-trainer-bot
    chess_bot_profile_url = f"https://lichess.org/@/{OUR_NAME}"
    try:
        webbrowser.open(chess_bot_profile_url, new=2)
        print(f"Opening browser at {chess_bot_profile_url}")
    except Exception as e:
        print(f"Couldn't open browser: {e}")

    try:
        handle_events(bot_profile=profile)
    except KeyboardInterrupt:
        print("Exiting")


if __name__ == "__main__":
    main()
