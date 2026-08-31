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

def find_stockfish_binary() -> Optional[str]:
    """Locate a Stockfish binary, or return ``None`` if none is installed.

    The UI needs to render even when the engine is missing, so this no longer
    raises; callers that actually need the engine (``play_game``) check for
    ``None`` and fail loudly there instead.
    """
    env_path = os.getenv("STOCKFISH_PATH")
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        return env_path
    default = "/usr/games/stockfish"
    if os.path.isfile(default) and os.access(default, os.X_OK):
        return default
    return shutil.which("stockfish")


def stockfish_version(path: Optional[str] = None) -> Optional[str]:
    """Return the Stockfish version string (e.g. ``"16"``), or ``None``.

    Runs the binary with a ``uci`` handshake and parses the ``id name`` line.
    """
    path = path or STOCKFISH_PATH
    if not path:
        return None
    try:
        import subprocess

        proc = subprocess.run(
            [path],
            input="uci\nquit\n",
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.lower().startswith("id name ") and "stockfish" in line.lower():
            # "id name Stockfish 16" / "id name Stockfish 16.1"
            return line.split("Stockfish", 1)[1].strip() or None
    return None


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
    if not STOCKFISH_PATH:
        raise FileNotFoundError(
            "Could not locate the Stockfish binary! Please install it or set STOCKFISH_PATH."
        )
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

###############################################
#   Reconnecting to games already in progress
###############################################

# Game ids we currently have a ``play_game`` loop running for. Shared across
# threads so the startup "resume" pass and the live event stream never both
# attach to the same game.
_ACTIVE_GAMES: set[str] = set()
_ACTIVE_GAMES_LOCK = threading.Lock()


def _claim_game(game_id: str) -> bool:
    """Register ``game_id`` as being played; return ``False`` if already claimed."""
    with _ACTIVE_GAMES_LOCK:
        if game_id in _ACTIVE_GAMES:
            return False
        _ACTIVE_GAMES.add(game_id)
        return True


def _release_game(game_id: str) -> None:
    with _ACTIVE_GAMES_LOCK:
        _ACTIVE_GAMES.discard(game_id)


def _play_game_guarded(game_id: str, bot_profile: BotProfile, on_game_start=None) -> None:
    """Run ``play_game`` once for ``game_id``, with dedup and error isolation."""
    if not _claim_game(game_id):
        print(f"Already playing {game_id}; not starting a second loop")
        return
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
    finally:
        _release_game(game_id)


def resume_ongoing_games(bot_profile: BotProfile, on_game_start=None) -> None:
    """Re-attach to any games already in progress on the bot account.

    Lichess replays a ``gameStart`` for in-progress games whenever the event
    stream re-opens, which already covers a dropped connection. Calling this
    explicitly (e.g. on app startup) means a restarted process picks its game
    back up without waiting for the user to submit the setup form again.

    Safe to call with an unconfigured profile: opening-book moves are simply
    skipped and the engine plays instead. Blocks until each resumed game ends,
    mirroring ``play_game``'s behaviour in the normal event loop.
    """
    if client is None:
        return
    try:
        ongoing = list(client.games.get_ongoing())
    except Exception as e:
        print(f"[resume] couldn't fetch ongoing games: {e}")
        return
    for game in ongoing:
        game_id = game.get("gameId") or game.get("fullId")
        if not game_id:
            continue
        print(f"Resuming ongoing game: {game_id}")
        _play_game_guarded(game_id, bot_profile, on_game_start)


def handle_events(
    bot_profile: BotProfile = BotProfile(),
    on_game_start=None,
    stop_event: Optional[threading.Event] = None,
):
    print("Listening for events now...")
    # Pick up anything already in progress before we start streaming, so a
    # reconnect after a crash/restart/network drop resumes the game right away.
    if not (stop_event and stop_event.is_set()):
        resume_ongoing_games(bot_profile, on_game_start)
    for event in robust_stream_incoming_events():
        if stop_event and stop_event.is_set():
            break
        t = event["type"]
        if t == "challenge":
            challenge = event.get("challenge", {})
            challenge_id = challenge.get("id")
            challenger = challenge.get("challenger", {})
            challenger_id = challenger.get("id")

            if not challenge_id:
                print("Received challenge event without an ID; skipping")
                continue

            if not bot_profile.is_challenge_allowed(challenger_id):
                name = challenger_id or "unknown"
                allowed_display = bot_profile.allowed_username or "specified user"
                print(
                    f"Declining challenge from {name}; "
                    f"only accepting challenges from {allowed_display}."
                )
                try:
                    client.bots.decline_challenge(challenge_id)
                except ResponseError as e:
                    print(f"Could not decline challenge; skipping - {e}")
                continue

            try:
                client.bots.accept_challenge(challenge_id)
            except ResponseError as e:
                print(f"Could not accept challenge; skipping - {e}")
            else:
                print("Accepted challenge!")
        elif t == "gameStart":
            game_id = event["game"]["id"]
            print(f"Game started: {game_id}")
            _play_game_guarded(game_id, bot_profile, on_game_start)

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
