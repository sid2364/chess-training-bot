from __future__ import annotations

import threading
import webbrowser
from typing import List, Optional

from flask import Flask, request, render_template
import requests
import html

from .trainer import (
    API_TOKEN,
    handle_events,
)
from .bot_profile import BotProfile, white_openings, black_openings

app = Flask(__name__)
PROFILE = BotProfile()

def build_options(name_list: List[str], field: str) -> str:
    out = []
    for opening in name_list:
        value = html.escape(opening, quote=True)
        label = html.escape(opening)
        out.append(
            f"<label><input type='checkbox' name='{field}' value='{value}'> {label}</label><br>"
        )
    return "\n".join(out)

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


@app.get("/")
def index() -> str:
    white = build_options(white_openings, "white")
    black = build_options(black_openings, "black")
    return render_template("index.html", white_options=white, black_options=black)

@app.post("/start")
def start() -> str:
    PROFILE.chosen_white = request.form.getlist("white")
    PROFILE.chosen_black = request.form.getlist("black")
    PROFILE.challenge = int(request.form.get("challenge", "0") or 0)
    username = request.form.get("username", "")

    print(PROFILE)
    url = create_challenge(username)
    if not url:
        return "Failed to create challenge"

    webbrowser.open(url)

    def on_game_start(game_id: str) -> None:
        webbrowser.open(f"https://lichess.org/{game_id}")

    thread = threading.Thread(
        target=handle_events, args=(PROFILE, on_game_start), daemon=True
    )
    thread.start()
    return "Challenge created. Please accept it in the opened tab."

def run_server() -> None:
    """Start the frontend server and launch the default browser."""
    threading.Timer(1, lambda: webbrowser.open("http://localhost:8000/")).start() # so we don't see a "connection refused before Flask starts serving

    app.run(host="localhost", port=8000)


if __name__ == "__main__":
    run_server()
