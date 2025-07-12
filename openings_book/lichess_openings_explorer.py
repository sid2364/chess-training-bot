import random
import os
import sys

# When run directly (e.g. ``python chess_trainer/lichess_openings_explorer.py``)
# we need to add the repository root to ``sys.path`` so that imports of the
# ``chess_trainer`` package succeed.
if __package__ is None or __package__ == "":
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
try:  # optional dependency for reading .env
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    def load_dotenv() -> None:
        pass
try:  # optional dependency for network requests
    import requests
except Exception:  # pragma: no cover - optional dependency
    requests = None
try:  # optional dependency for board representation
    import chess
except Exception:  # pragma: no cover - optional dependency
    chess = None

try:  # berserk is optional during testing
    import berserk
except Exception:  # pragma: no cover - optional dependency
    berserk = None

# local opening book utilities (may not be present??)
try:
    from openings_book import query_db as local_db
except Exception:  # pragma: no cover - optional dependency
    local_db = None


"""Utilities for fetching and filtering opening moves from Lichess."""

# Use an absolute import so this module works when executed directly or as part
# of the ``chess_trainer`` package.
from chess_trainer.bot_profile import BotProfile

load_dotenv()  # read .env for API token if present
API_TOKEN = os.getenv("LICHESS_BOT_TOKEN")
lichess_explorer_url = "https://explorer.lichess.ovh/masters"

LOCAL_BOOK_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "opening_book.json")
if local_db is not None and os.path.exists(LOCAL_BOOK_PATH):
    try:
        _LOCAL_BOOK = local_db.load_trie(LOCAL_BOOK_PATH)
    except Exception:  # pragma: no cover - optional dependency
        _LOCAL_BOOK = None
else:  # pragma: no cover - optional dependency
    _LOCAL_BOOK = None

if berserk is not None and API_TOKEN:
    session = berserk.TokenSession(API_TOKEN)
    client = berserk.Client(session=session)
    explorer = client.opening_explorer
else:  # pragma: no cover - used when testing without network
    session = client = explorer = None

def fetch_book_moves(play, top_n):
    if requests is None:
        raise RuntimeError("requests library is required to fetch openings")

    params = {"play": play, "moves": top_n}
    resp = requests.get(lichess_explorer_url, params=params)
    return resp.json().get("moves", [])

def get_local_book_moves(board, top_n):
    """Return moves from the local opening book for the given position."""
    if _LOCAL_BOOK is None or local_db is None:
        # print("local_db or _LOCAL_BOOK is None")
        return []

    node = local_db.get_node_by_path(_LOCAL_BOOK, [m.uci() for m in board.move_stack])
    children = node.get("children") or {}
    moves = []
    # print(f"CHILDREN {children}")
    for uci, child in children.items():
        stats = child.get("stats") or [0, 0, 0]
        entry = {
            "uci": uci,
            "white": stats[0],
            "draws": stats[1],
            "black": stats[2],
        }
        name = child.get("opening_name")
        if name:
            entry["opening"] = {"name": name}
        moves.append(entry)

    if top_n is not None and len(moves) > top_n:
        moves.sort(key=lambda m: m["white"] + m["draws"] + m["black"], reverse=True)
        moves = moves[:top_n]

    return moves



def filter_by_preferences(moves, prefs):
    """
    Given a list of opening move dicts and a list of preferred opening substrings, return only those dicts whose opening.name contains any of the prefs
    """
    # print("MOVES", moves)
    # print("PREFS", prefs)
    if not prefs:
        return moves

    prefs_lower = [p.lower() for p in prefs]

    named = []
    for m in moves:
        # m.get("opening") might be None, so use `or {}`
        opening = m.get("opening") or {}
        name = opening.get("name")
        if name:
            named.append((m, name.lower()))

    # if there are named‐opening moves, try to filter those
    if named:
        # full matches: name_lower == any pref_lower
        full = [m for (m, name_lower) in named if name_lower in prefs_lower]
        if full:
            return full

        # partial matches: pref in name_lower or name_lower in pref
        partial = [
            m for (m, name_lower) in named
            if any(pref in name_lower or name_lower in pref for pref in prefs_lower)
        ]
        if partial:
            return partial

        # fallback: keep all named-opening moves
        return [m for (m, _) in named]

    # no named openings so just return everything sinc we can't filter
    return moves

def get_book_move(board, bot_profile: BotProfile, max_ply=20, top_n=5):
    ply = len(board.move_stack)
    if ply >= max_ply:
        return None

    play = ",".join(m.uci() for m in board.move_stack) if ply else None

    # response = fetch_book_moves(play, top_n)
    # first try local database
    response = get_local_book_moves(board, top_n)
    if not response:
        print("Using Lichess API to fetch the best book moves")
        response = fetch_book_moves(play, top_n)
    else:
        print("Found book moves in local DB")

    # figure out prefs
    if chess is None:
        prefs = bot_profile.get_clean_openings()[0]
    else:
        white_prefs, black_prefs = bot_profile.get_clean_openings()
        prefs = white_prefs if bot_profile.our_color == chess.WHITE else black_prefs

    # unfiltered UCIs for debug
    unfiltered_moves = [m['uci'] for m in response]

    # apply your prefs filter
    filtered_moves = filter_by_preferences(response, prefs)
    if not filtered_moves:
        return None

    # compute weights on filtered only
    weights = [
        m['white'] + m['draws'] + m['black']
        for m in filtered_moves
    ]
    filtered_uci = [m['uci'] for m in filtered_moves]

    # weighted random pick
    chosen = random.choices(population=filtered_uci, weights=weights, k=1)[0]

    print("*" * 20)
    print(f"Unfiltered: {unfiltered_moves}")
    print(f"After filter: {filtered_uci}")
    print(f"Weights: {weights}")
    print(f"Chosen move: {chosen}")

    return chosen