from __future__ import annotations

import threading
import webbrowser
from typing import Callable, List, Optional

from flask import Flask, request
import requests

from .trainer import (
    API_TOKEN,
    BotProfile,
    handle_events,
    white_openings,
    black_openings,
)

app = Flask(__name__)
PROFILE = BotProfile()

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8'>
    <title>Chess Trainer Setup</title>
</head>
<body>
    <h1>Chess Trainer Bot Setup</h1>
    <form method='post' action='/start'>
        <h2>White openings</h2>
        {white_options}
        <h2>Black openings</h2>
        {black_options}
        <label>Challenge rating offset:
            <input type='number' name='challenge' value='0'>
        </label><br>
        <label>Your Lichess username:
            <input type='text' name='username'>
        </label><br>
        <button type='submit'>Start Game</button>
    </form>
</body>
</html>"""


def build_options(name_list: List[str], field: str) -> str:
    out = []
    for opening in name_list:
        safe = opening.replace('"', '&quot;')
        out.append(
            f"<label><input type='checkbox' name='{field}' value='{safe}'> {safe}</label><br>"
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
    return json_data.get("challenge", {}).get("url")


@app.get("/")
def index() -> str:
    white = build_options(white_openings, "white")
    black = build_options(black_openings, "black")
    return HTML_TEMPLATE.format(white_options=white, black_options=black)


@app.post("/start")
def start() -> str:
    PROFILE.chosen_white = request.form.getlist("white")
    PROFILE.chosen_black = request.form.getlist("black")
    PROFILE.challenge = int(request.form.get("challenge", "0") or 0)
    username = request.form.get("username", "")
    url = create_challenge(username)
    return url or "Failed to create challenge"


def run_server() -> None:
    """Start the frontend server and launch the default browser."""

    def on_game_start(game_id: str) -> None:
        webbrowser.open(f"https://lichess.org/{game_id}")

    thread = threading.Thread(
        target=handle_events, args=(PROFILE, on_game_start), daemon=True
    )
    thread.start()
    webbrowser.open("http://localhost:8000/")
    app.run(host="localhost", port=8000)


if __name__ == "__main__":
    run_server()
