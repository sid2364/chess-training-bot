import chess_trainer.openings_explorer as oe

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

