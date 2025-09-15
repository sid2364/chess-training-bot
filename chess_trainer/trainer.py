#!/usr/bin/env python3
import os
import sys
import shutil
import threading
import time
import traceback
from typing import Optional

# ---- new imports for retry logic ----
import requests
from requests import HTTPError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import retry, stop_after_attempt, wait_random_exponential

import webbrowser
from berserk.exceptions import ResponseError

# When executed directly, add project root so absolute imports work
if __package__ is None or __package__ == "":
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# optional .env support
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> None:
        pass

try:
    import berserk
except ImportError:
    berserk = None

try:
    import chess
    import chess.engine
except ImportError:
    chess = None

from chess_trainer.bot_profile import BotProfile
from opening_book import lichess_openings_explorer

load_dotenv()
API_TOKEN = os.getenv("LICHESS_BOT_TOKEN")
OUR_NAME = os.getenv("LICHESS_BOT_NAME")
TIME_PER_MOVE = 2

def find_stockfish_binary() -> str:
    env_path = os.getenv("STOCKFISH_PATH")
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        return env_path
    default = "/usr/games/stockfish"
    if os.path.isfile(default) and os.access(default, os.X_OK):
        return default
    which = shutil.which("stockfish")
    if which:
        return which
    raise FileNotFoundError(
        "Could not locate the Stockfish binary! Please install it or set STOCKFISH_PATH."
    )

STOCKFISH_PATH = find_stockfish_binary()

# ---- set up berserk with a retrying session ----
if berserk is not None and API_TOKEN:
    # create a requests.Session with retries
    base_session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    base_session.mount("http://", adapter)
    base_session.mount("https://", adapter)

    # TokenSession wraps base_session internally; we monkey‑patch it:
    token_sess = berserk.TokenSession(API_TOKEN)
    token_sess.session = base_session

    session = token_sess
    client = berserk.Client(session=session)
else:
    session = client = None

###############################################
#   Robust streaming helpers with backoff
###############################################

def robust_stream_incoming_events():
    backoff = 5
    while True:
        try:
            for event in client.bots.stream_incoming_events():
                yield event
            backoff = 5
        except Exception as e:
            print(f"[stream_incoming_events] error: {e}; reconnecting in {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)

def robust_stream_game_state(game_id):
    backoff = 5
    while True:
        try:
            for ev in client.bots.stream_game_state(game_id):
                yield ev
            backoff = 5
        except Exception as e:
            print(f"[stream_game_state] error: {e}; reconnecting in {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)

###############################################
#   Decorated move sender with retry
###############################################

@retry(stop=stop_after_attempt(3), wait=wait_random_exponential(multiplier=1, max=10))
def make_move_on_board(board, game_id, chosen_move_uci):
    try:
        client.bots.make_move(game_id, chosen_move_uci)
    except ResponseError as e:
        print(f"Could not make move {chosen_move_uci}: {e}; retrying...")
        raise
    except HTTPError as e:
        print(f"Lichess returned error: {e}. Won't retry, moving on to the next game!")
        return
    board.push_uci(chosen_move_uci)

###############################################
#   Core Bot Logic
###############################################

def play_game(game_id, bot_profile: BotProfile):
    # print("in play_game, bot_profile=", bot_profile)
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    stream = robust_stream_game_state(game_id)

    # handle initial state
    start = next(stream)
    bot_profile.determine_color_and_opp_rating(start) # TODO could be run implicitly before play_game?
    print(f"Playing as {'White' if bot_profile.our_color else 'Black'} vs {bot_profile.opp_rating}")
    bot_profile.opp_rating = max(1320, min(3190, bot_profile.opp_rating + bot_profile.challenge))
    engine.configure({
        "UCI_LimitStrength": True,
        "UCI_Elo": bot_profile.opp_rating,
        "Threads": 4
    })

    # rebuild board
    init_moves = start.get("state", {}).get("moves", "").split()
    board = chess.Board()
    for idx, uci in enumerate(init_moves, start=1):
        board.push_uci(uci)

    # if it's our turn
    if board.turn == bot_profile.our_color:
        chosen = lichess_openings_explorer.get_book_move(board, bot_profile)
        if not chosen:
            move = engine.play(board, limit=chess.engine.Limit(time=TIME_PER_MOVE)).move.uci()
            make_move_on_board(board, game_id, move)
            print(f"-> (engine) {move}")
        else:
            make_move_on_board(board, game_id, chosen)
            print(f"-> (book) {chosen}")
    else:
        print("Waiting for opponent...")

    # main loop
    for ev in stream:
        # only care about game-state updates
        if ev.get("type") != "gameState":
            continue

        # if the game is no longer 'started', stop here
        status = ev.get("status")
        if status != "started":
            winner = ev.get("winner") or "none"
            print(f"Game ended: status={status}, winner={winner}")
            break

        # rebuild the board from the moves string
        board.reset()
        for uci in ev["moves"].split():
            board.push_uci(uci)

        # if it’s our turn, pick and send a move
        if board.turn == bot_profile.our_color:
            chosen = lichess_openings_explorer.get_book_move(board, bot_profile)
            if not chosen:
                engine_move = engine.play(board, limit=chess.engine.Limit(time=TIME_PER_MOVE))
                # engine_move.move should always be valid here
                chosen = engine_move.move.uci()
            make_move_on_board(board, game_id, chosen)
            print(f"-> {chosen}")

    engine.quit()

def handle_events(
    bot_profile: BotProfile = BotProfile(),
    on_game_start=None,
    stop_event: Optional[threading.Event] = None,
):
    print("Listening for events now...")
    for event in robust_stream_incoming_events():
        if stop_event and stop_event.is_set():
            break
        t = event["type"]
        if t == "challenge":
            try:
                client.bots.accept_challenge(event["challenge"]["id"])
            except ResponseError as e:
                print(f"Could not accept challenge; skipping - {e}")
            else:
                print("Accepted challenge!")
        elif t == "gameStart":
            game_id = event["game"]["id"]
            print(f"Game started: {game_id}")
            if on_game_start:
                try:
                    on_game_start(game_id)
                except Exception:
                    pass
            try:
                play_game(game_id, bot_profile)
            except Exception as e:
                traceback.print_exc()
                print(f"Game discontinued, moving on: {e}")

def main() -> None:
    profile = BotProfile()
    try:
        profile.get_openings_choice_from_user()
    except KeyboardInterrupt:
        print("Exiting"); return

    white, black = profile.get_clean_openings()
    print(f"As White -> {', '.join(white)}; as Black -> {', '.join(black)}")

    try:
        webbrowser.open(f"https://lichess.org/@/{OUR_NAME}", new=2)
    except Exception as e:
        print(f"Couldn't open browser: {e}")

    try:
        handle_events(bot_profile=profile)
    except KeyboardInterrupt:
        print("Exiting")

if __name__ == "__main__":
    main()
