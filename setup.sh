#!/usr/bin/env bash
set -euo pipefail

# --- Install or locate Stockfish ------------------------------------------------------
command -v stockfish >/dev/null 2>&1 || {
    echo "Stockfish binary not found – attempting to install via apt-get." 
    if command -v apt-get >/dev/null 2>&1; then
        SUDO="sudo"
        if [[ ${EUID:-$(id -u)} -eq 0 ]] || ! command -v sudo >/dev/null 2>&1; then
            SUDO=""
        fi
        if ${SUDO:+$SUDO }apt-get update && ${SUDO:+$SUDO }apt-get install -y stockfish; then
            echo "Stockfish installed successfully."
        else
            echo "Warning: apt-get was unable to install Stockfish. Please install it manually and/or set STOCKFISH_PATH."
        fi
    else
        echo "Warning: apt-get is not available on this system. Install Stockfish manually and/or set STOCKFISH_PATH."
    fi
}

if command -v stockfish >/dev/null 2>&1; then
    echo "Detected Stockfish binary: $(command -v stockfish)"
    stockfish -? 2>/dev/null | head -n 1 || true
else
    echo "Warning: Stockfish binary still not found. The bot will require STOCKFISH_PATH to be set."
fi

# --- Python dependencies --------------------------------------------------------------
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=$(command -v python3)
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=$(command -v python)
else
    echo "Error: Python 3 is required but was not found in PATH." >&2
    exit 1
fi

echo "Installing Python dependencies with $PYTHON_BIN..."
if ! "$PYTHON_BIN" -m pip install -r requirements.txt; then
    echo "Error: failed to install Python dependencies. Please check your internet connection or proxy settings." >&2
    exit 1
fi

# --- Frontend build -------------------------------------------------------------------
if command -v npm >/dev/null 2>&1; then
    npm install
    npm run build
else
    echo "Warning: npm is not installed; skipping frontend build."
fi
