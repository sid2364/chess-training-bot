import random
import berserk
import os
from dotenv import load_dotenv
import requests


load_dotenv() # to read .env
API_TOKEN = os.getenv("LICHESS_BOT_TOKEN")

session = berserk.TokenSession(API_TOKEN)
client = berserk.Client(session=session)
explorer = client.opening_explorer


def fetch_book_moves(play, top_n):
    url = "https://explorer.lichess.ovh/lichess"
    params = {"play": play, "moves": top_n}
    # headers = {"Authorization": f"Bearer {API_TOKEN}"}
    resp = requests.get(url, params=params) #, headers=headers)
    return resp.json().get("moves", [])


def get_book_move(board, max_ply=20, top_n=3): # top_n is the number of moves to choose from
    ply = len(board.move_stack)
    if ply >= max_ply:
        return None

    play = ",".join(m.uci() for m in board.move_stack) if ply else None

    # response = explorer.get_lichess_games(play=play, moves=top_n)
    response = fetch_book_moves(play, top_n)
    candidates = [entry['uci'] for entry in response]

    if not candidates:
        return None

    choice = random.choice(candidates)
    print(f"Candidate moves: {candidates}, chose: {choice}")
    return choice