#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import berserk
import chess, chess.engine

load_dotenv() # to read .env
API_TOKEN = os.getenv("LICHESS_BOT_TOKEN")
if not API_TOKEN:
    raise RuntimeError("LICHESS_BOT_TOKEN not set in .env")

STOCKFISH_PATH = "/usr/games/stockfish"
# TODO check if the binary actually exists in this path, if not, do "which stockfish" and use that path instead

OUR_NAME = "chess-trainer-bot" # to identify our name on Lichess
TIME_PER_MOVE = 5 # just to not get rate limited
CHALLENGE = 100 # how much to increase bot ELO compared to player's

session = berserk.TokenSession(API_TOKEN)
client  = berserk.Client(session=session)

def handle_events():
    for event in client.bots.stream_incoming_events():
        t = event["type"]
        if t == "challenge":
            client.bots.accept_challenge(event["challenge"]["id"])
            print("Accepted challenge!")
        elif t == "gameStart":
            game_id = event["game"]["id"]
            print(f"Game started: {game_id}")
            play_game(game_id)

def play_game(game_id):
    # Launch engine
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    stream = client.bots.stream_game_state(game_id)
    board  = chess.Board()

    # First message contains players’ ratings
    start = next(stream)
    # print(start)
    """
    {
        'id': '4FOwDIIn', 
        'variant': {'key': 'standard', 'name': 'Standard', 'short': 'Std'},
        'speed': 'rapid',
        'perf': {'name': 'Rapid'},
        'rated': False,
        'createdAt': datetime.datetime(2025, 6, 19, 22, 25, 48, 138000, tzinfo=datetime.timezone.utc),
        'white': {'id': 'wolfpacktwentythree', 'name': 'WolfpackTwentyThree', 'title': None, 'rating': 1778},
        'black': {'id': 'chess-trainer-bot', 'name': 'chess-trainer-bot', 'title': 'BOT', 'rating': 2000, 'provisional': True},
        'initialFen': 'startpos',
        'clock': {'initial': 600000, 'increment': 5000},
        'type': 'gameFull',
        'state': {'type': 'gameState', 'moves': '', 'wtime': 600000, 'btime': 600000, 'winc': 5000, 'binc': 5000, 'status': 'started'}
    }
    """
    white = start["white"]
    black = start["black"]

    # Determine our color and opponent rating
    if white["id"] == OUR_NAME:
        our_color = chess.WHITE
        opp_rating = black["rating"]
    else:
        our_color = chess.BLACK
        opp_rating = white["rating"]

    opp_rating += CHALLENGE
    # Configure Stockfish to match opponent’s strength
    engine.configure({
        "UCI_LimitStrength": True,
        "UCI_Elo": opp_rating
    })
    print(f"Playing as {'White' if our_color else 'Black'} vs {opp_rating - CHALLENGE}-rated opponent")

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

    if board.turn == our_color:
        print("It's the BOT's turn!")
        result = engine.play(board, limit=chess.engine.Limit(time=TIME_PER_MOVE))
        client.bots.make_move(game_id, result.move.uci())
        board.push(result.move)  # update our local board
        print(f"-> (first move) {result.move.uci()}")
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
        if board.turn == our_color:
            result = engine.play(board, limit=chess.engine.Limit(time=TIME_PER_MOVE))
            client.bots.make_move(game_id, result.move.uci())
            print(f"-> {result.move.uci()}")

    engine.quit()

if __name__ == "__main__":
    print("Starting bot...")
    handle_events()
