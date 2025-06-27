#!/usr/bin/env bash
set -e

# Install Stockfish 16 via apt-get
sudo apt-get update
# Try to install the stockfish package. Many modern distributions package
# Stockfish 16 under the default "stockfish" name.
# If your repository doesn't provide version 16, you may need to add an
# appropriate PPA or download the binary manually.
sudo apt-get install -y stockfish

# Verify installation
if stockfish -? 2>/dev/null | head -n 1 | grep -q "Stockfish 16"; then
    echo "Stockfish 16 installed successfully."
else
    echo "Warning: Stockfish 16 was not detected."
fi

# Install Python dependencies
pip install -r requirements.txt
