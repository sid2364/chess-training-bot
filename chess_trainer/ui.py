from __future__ import annotations

import threading
import webbrowser
from typing import List, Optional
import sys
import os

# When executed directly (``python chess_trainer/ui.py``) we need the project
# root on ``sys.path`` so absolute imports work.
if __package__ is None or __package__ == "":
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, render_template, jsonify
import requests
import json

from opening_book import query_db

# When this module is run directly ``__package__`` will be ``None`` and relative
# imports will fail.  Using absolute imports keeps things working in that
# scenario as well as when the package is imported.
from chess_trainer.trainer import (
    API_TOKEN,
    handle_events,
    OUR_NAME
)
from chess_trainer.bot_profile import BotProfile

app = Flask(__name__)
PROFILE = BotProfile()
EVENT_THREAD: Optional[threading.Thread] = None
STOP_EVENT: Optional[threading.Event] = None

BOOK_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "opening_book.json")
BOOK = query_db.load_trie(BOOK_PATH)

def create_challenge(username: str) -> Optional[str]:
    """Send a challenge to ``username`` using the Lichess API."""
    if not API_TOKEN:
        return None
    url = f"https://lichess.org/api/challenge/{username}"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    data = {
        "rated": "false",
        "clock.limit": 600,
        "clock.increment": 5,
    }
    resp = requests.post(url, headers=headers, data=data)
    if resp.status_code not in (200, 201):
        return None
    json_data = resp.json()
    return json_data.get("url", {})


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    message: Optional[str] = None
    if request.method == "POST":
        global EVENT_THREAD, STOP_EVENT
        white_raw = request.form.get("white", "")
        black_raw = request.form.get("black", "")
        PROFILE.chosen_white = [w for w in white_raw.split(",") if w]
        PROFILE.chosen_black = [b for b in black_raw.split(",") if b]
        PROFILE.challenge = int(request.form.get("challenge", "0") or 0)
        username = request.form.get("username", "")

        print(PROFILE)
        url = create_challenge(username)
        if not url:
            message = "Failed to create challenge"
        else:
            webbrowser.open(url)

            if EVENT_THREAD is not None and EVENT_THREAD.is_alive():
                if STOP_EVENT is not None:
                    STOP_EVENT.set()
                EVENT_THREAD.join(timeout=0.1)

            STOP_EVENT = threading.Event()

            def on_game_start(game_id: str) -> None:
                # webbrowser.open(f"https://lichess.org/{game_id}")
                pass # we already open the challenge above when we get the url back, so no need to open twice

            EVENT_THREAD = threading.Thread(
                target=handle_events,
                args=(PROFILE, on_game_start, STOP_EVENT),
                daemon=True,
            )
            EVENT_THREAD.start()
            message = "Challenge sent!"

    return render_template(
        "index.html",
        selected_white=",".join(PROFILE.chosen_white),
        selected_black=",".join(PROFILE.chosen_black),
        message=message,
        challenge=PROFILE.challenge,
    )

@app.route("/profile", methods=["POST"])
def profile() -> str:
    """Save settings and open the bot profile page in the user's browser."""
    global EVENT_THREAD, STOP_EVENT

    white_raw = request.form.get("white", "")
    black_raw = request.form.get("black", "")
    PROFILE.chosen_white = [w for w in white_raw.split(",") if w]
    PROFILE.chosen_black = [b for b in black_raw.split(",") if b]
    PROFILE.challenge = int(request.form.get("challenge", "0") or 0)

    url = f"https://lichess.org/@/{OUR_NAME}"
    try:
        webbrowser.open(url, new=2)
    except Exception:
        pass

    if EVENT_THREAD is not None and EVENT_THREAD.is_alive():
        if STOP_EVENT is not None:
            STOP_EVENT.set()
        EVENT_THREAD.join(timeout=0.1)

    STOP_EVENT = threading.Event()

    EVENT_THREAD = threading.Thread(
        target=handle_events,
        args=(PROFILE, None, STOP_EVENT),
        daemon=True,
    )
    EVENT_THREAD.start()

    return render_template(
        "index.html",
        selected_white=",".join(PROFILE.chosen_white),
        selected_black=",".join(PROFILE.chosen_black),
        message="Bot profile saved, ready for challenges!",
        challenge=PROFILE.challenge,
    )


@app.route("/openings")
def openings() -> str:
    path_str = request.args.get("path", "").strip()
    q = request.args.get("q", "").strip()
    path = path_str.split() if path_str else []
    node = query_db.get_node_by_path(BOOK, path)

    if q:
        matches = query_db.find_matching_nodes(node, [q])
        results = []
        for p, n, _ in matches:
            name = n.get("opening_name")
            if name:
                full = path + p
                results.append({"path": " ".join(full), "name": name})
        return jsonify({"results": results})

    children = []
    for uci, child in (node.get("children") or {}).items():
        children.append({
            "uci": uci,
            "name": child.get("opening_name"),
            "eco": child.get("eco"),
            "hasChildren": bool(child.get("children")),
        })
    return jsonify({"path": " ".join(path), "children": children})

def run_server() -> None:
    """Start the frontend server and launch the default browser."""
    threading.Timer(1, lambda: webbrowser.open("http://localhost:8000/")).start() # timer of 1 so we don't see a "connection refused" before Flask starts serving

    app.run(host="localhost", port=8000)


if __name__ == "__main__":
    run_server()
