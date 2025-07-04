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
    OUR_NAME
)
from .bot_profile import BotProfile, white_openings, black_openings

app = Flask(__name__)
PROFILE = BotProfile()
EVENT_THREAD: Optional[threading.Thread] = None
STOP_EVENT: Optional[threading.Event] = None

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


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    message: Optional[str] = None
    if request.method == "POST":
        global EVENT_THREAD, STOP_EVENT
        PROFILE.chosen_white = request.form.getlist("white")
        PROFILE.chosen_black = request.form.getlist("black")
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

    white = build_options(white_openings, "white")
    black = build_options(black_openings, "black")
    return render_template(
        "index.html", white_options=white, black_options=black, message=message
    )

@app.route("/profile", methods=["POST"])
def profile() -> str:
    """Save settings and open the bot profile page in the user's browser."""
    global EVENT_THREAD, STOP_EVENT

    PROFILE.chosen_white = request.form.getlist("white")
    PROFILE.chosen_black = request.form.getlist("black")
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

    white = build_options(white_openings, "white")
    black = build_options(black_openings, "black")
    return render_template(
        "index.html",
        white_options=white,
        black_options=black,
        message="Bot profile saved, ready for challenges!",
    )


def run_server() -> None:
    """Start the frontend server and launch the default browser."""
    threading.Timer(1, lambda: webbrowser.open("http://localhost:8000/")).start() # so we don't see a "connection refused before Flask starts serving

    app.run(host="localhost", port=8000)


if __name__ == "__main__":
    run_server()
