import os
import sys

# to ensure the package can be imported when tests are run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import openings_book.lichess_openings_explorer as oe

sample_moves = [
    {"uci": "e2e4", "opening": {"name": "King's Pawn Game"}},
    {"uci": "d2d4", "opening": {"name": "Queen's Pawn Game"}},
]

def test_no_preferences_returns_all():
    result = oe.filter_by_preferences(sample_moves, None)
    assert result == sample_moves

def test_exact_match():
    result = oe.filter_by_preferences(sample_moves, ["King's Pawn Game"])
    assert result == [sample_moves[0]]

def test_partial_match():
    result = oe.filter_by_preferences(sample_moves, ["Queen's"])
    assert result == [sample_moves[1]]

