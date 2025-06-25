import random
import berserk
import os
from dotenv import load_dotenv
import requests
import chess

from trainer import BotProfile

load_dotenv() # to read .env
API_TOKEN = os.getenv("LICHESS_BOT_TOKEN")
lichess_explorer_url = "https://explorer.lichess.ovh/lichess"

session = berserk.TokenSession(API_TOKEN)
client = berserk.Client(session=session)
explorer = client.opening_explorer

def fetch_book_moves(play, top_n):
    params = {"play": play, "moves": top_n}
    print(params)
    # headers = {"Authorization": f"Bearer {API_TOKEN}"}
    resp = requests.get(lichess_explorer_url, params=params) #, headers=headers)
    return resp.json().get("moves", [])


def filter_by_preferences(moves, prefs):
    """
    Given a list of opening move dicts and a list of preferred opening substrings, return only those dicts whose opening.name contains any of the prefs
    """
    print("MOVES", moves)
    print("PREFS", prefs)
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

def get_book_move(board, bot_profile: BotProfile, max_ply=20, top_n=10): # top_n is the number of moves to choose from
    ply = len(board.move_stack)
    if ply >= max_ply:
        return None

    play = ",".join(m.uci() for m in board.move_stack) if ply else None

    # response = explorer.get_lichess_games(play=play, moves=top_n)
    response = fetch_book_moves(play, top_n)

    # figure out which preference list to use
    white_prefs, black_prefs = bot_profile.get_clean_openings()
    print(white_prefs, black_prefs)
    prefs = white_prefs if bot_profile.our_color == chess.WHITE else black_prefs

    filtered = filter_by_preferences(response, prefs)
    unfiltered = filter_by_preferences(response, None)

    candidates = [entry['uci'] for entry in filtered]
    all_candidates = [entry['uci'] for entry in unfiltered]

    if not candidates:
        return None

    choice = random.choice(candidates)
    print(f"Candidate moves before filtering: {all_candidates},\n after filtering: {candidates},\n chose: {choice}")
    return choice