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
import html

# Helper to load and walk the trie
from opening_book.crawler import OPENING_BOOK_FILE
import json

# When this module is run directly ``__package__`` will be ``None`` and relative
# imports will fail.  Using absolute imports keeps things working in that
# scenario as well as when the package is imported.
from chess_trainer.trainer import (
    API_TOKEN,
    handle_events,
    OUR_NAME
)
from chess_trainer.bot_profile import BotProfile, white_openings, black_openings

app = Flask(__name__)
PROFILE = BotProfile()
EVENT_THREAD: Optional[threading.Thread] = None
STOP_EVENT: Optional[threading.Event] = None

def build_options(name_list: List[str], field: str, selected: Optional[List[str]] = None) -> str:
    out = []
    selected_set = set(selected or [])
    for opening in name_list:
        value = html.escape(opening, quote=True)
        label = html.escape(opening)
        checked = " checked" if opening in selected_set else ""
        out.append(
            f"<label><input type='checkbox' name='{field}' value='{value}'{checked}> {label}</label><br>"
        )
    return "\n".join(out)

def create_challenge(username: str, color: str) -> Optional[str]:
    """Send a challenge to ``username`` using the Lichess API."""
    if not API_TOKEN:
        return None
    url = f"https://lichess.org/api/challenge/{username}"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    data = {
        "rated": "false",
        "clock.limit": 600,
        "clock.increment": 5,
        "color": color,
    }
    resp = requests.post(url, headers=headers, data=data)
    if resp.status_code not in (200, 201):
        return None
    json_data = resp.json()
    return json_data.get("url", {})

def load_trie():
    with open(OPENING_BOOK_FILE, encoding="utf-8") as f:
        return json.load(f)

def get_subtree(node: dict):
    """Return list of children with uci, optional opening_name."""
    out = []
    for uci, child in node.get("children", {}).items():
        out.append({
            "uci": uci,
            "opening_name": child.get("opening_name"),
        })
    return out

@app.route("/api/openings")
def api_openings():
    side = request.args.get("side")
    path = request.args.getlist("path[]")  # ["e2e4","g1f3",…]
    trie = load_trie()
    # If black, skip white’s first move: e.g. path[0] is white’s 1st, so we start at trie.children[path[0]].children
    node = trie
    for move in path:
        node = node.get("children", {}).get(move, {})
    return jsonify({
        "children": get_subtree(node)
    })

@app.route("/api/openings/search")
def api_search():
    q = request.args.get("q", "")
    limit = int(request.args.get("limit", 50))
    # reuse your query_db.find_matching_nodes
    from opening_book.query_db import load_trie, find_matching_nodes
    trie = load_trie(OPENING_BOOK_FILE)
    matches = find_matching_nodes(trie, [q])
    results = []
    for path, node, _ in matches[:limit]:
        results.append({
            "path": path,
            "opening_name": node.get("opening_name"),
        })
    return jsonify({ "matches": results })

@app.route("/", methods=["GET", "POST"])
def index() -> str:
    message: Optional[str] = None
    if request.method == "POST":
        global EVENT_THREAD, STOP_EVENT
        openings = request.form.getlist("openings")
        if openings:
            PROFILE.chosen_white = openings
            PROFILE.chosen_black = openings
        else:
            PROFILE.chosen_white = request.form.getlist("white")
            PROFILE.chosen_black = request.form.getlist("black")
        PROFILE.challenge = int(request.form.get("challenge", "0") or 0)
        username = (request.form.get("username", "") or "").strip()
        PROFILE.allow_all_challengers = bool(request.form.get("allow_all"))
        PROFILE.allowed_username = username or None

        color = request.form.get("color", "random")
        if color not in {"white", "black", "random"}:
            color = "random"
        PROFILE.preferred_color = color

        if not username:
            message = "Please provide a username to challenge."
        else:
            print(PROFILE)
            url = create_challenge(username, PROFILE.preferred_color)
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

    white = build_options(white_openings, "white", PROFILE.chosen_white)
    black = build_options(black_openings, "black", PROFILE.chosen_black)
    return render_template(
        "index.html",
        white_options=white,
        black_options=black,
        message=message,
        challenge=PROFILE.challenge,
        username=PROFILE.allowed_username or "",
        allow_all=PROFILE.allow_all_challengers,
        color=PROFILE.preferred_color,
    )

@app.route("/profile", methods=["POST"])
def profile() -> str:
    """Save settings and open the bot profile page in the user's browser."""
    global EVENT_THREAD, STOP_EVENT

    openings = request.form.getlist("openings")
    if openings:
        PROFILE.chosen_white = openings
        PROFILE.chosen_black = openings
    else:
        PROFILE.chosen_white = request.form.getlist("white")
        PROFILE.chosen_black = request.form.getlist("black")
    PROFILE.challenge = int(request.form.get("challenge", "0") or 0)
    username = (request.form.get("username", "") or "").strip()
    PROFILE.allow_all_challengers = bool(request.form.get("allow_all"))
    PROFILE.allowed_username = username or None

    color = request.form.get("color", "random")
    if color not in {"white", "black", "random"}:
        color = "random"
    PROFILE.preferred_color = color

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

    white = build_options(white_openings, "white", PROFILE.chosen_white)
    black = build_options(black_openings, "black", PROFILE.chosen_black)
    return render_template(
        "index.html",
        white_options=white,
        black_options=black,
        message="Bot profile saved, ready for challenges!",
        challenge=PROFILE.challenge,
        username=PROFILE.allowed_username or "",
        allow_all=PROFILE.allow_all_challengers,
        color=PROFILE.preferred_color,
    )

def run_server() -> None:
    """Start the frontend server and launch the default browser."""
    threading.Timer(1, lambda: webbrowser.open("http://localhost:8000/")).start() # timer of 1 so we don't see a "connection refused" before Flask starts serving

    app.run(host="localhost", port=8000)


if __name__ == "__main__":
    run_server()
