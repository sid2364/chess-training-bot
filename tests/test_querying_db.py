import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openings_book import query_db

BOOK_PATH = os.path.join(os.path.dirname(__file__), "..", "opening_book.json") # kinda depends on there being a .json already?


def load_book():
    return query_db.load_trie(BOOK_PATH)


def test_load_trie_has_e2e4():
    trie = load_book()
    assert 'e2e4' in trie.get('children', {})


def test_get_node_by_path():
    trie = load_book()
    node = query_db.get_node_by_path(trie, ['e2e4', 'c7c5'])
    assert node.get('opening_name') == 'Sicilian Defense'
    assert node.get('stats') == [179913, 240745, 147001]


def test_find_matching_nodes_path_exists():
    trie = load_book()
    matches = query_db.find_matching_nodes(trie, ['Hyperaccelerated Dragon'])
    paths = [p for p, _, _ in matches]
    assert ['e2e4', 'c7c5', 'g1f3', 'g7g6'] in paths


def test_collect_full_continuations():
    trie = load_book()
    node = query_db.get_node_by_path(trie, ['e2e4', 'c7c5', 'g1f3', 'g7g6'])
    leaves = query_db.collect_full_continuations(['e2e4', 'c7c5', 'g1f3', 'g7g6'], node)
    assert ['e2e4', 'c7c5', 'g1f3', 'g7g6', 'd2d4'] in leaves
    assert len(leaves) == 6


def test_candidate_moves_for_italian_game():
    trie = load_book()
    res = query_db.candidate_moves_for_position(trie, ['Italian Game'], ['e2e4', 'e7e5', 'g1f3'])
    assert list(res.keys()) == ['b8c6']
    info = res['b8c6']
    assert info['stats'] == [66665, 113183, 46961]
    assert info['queried'] == ['Italian Game']
    assert 'e2e4 e7e5 g1f3 b8c6 f1c4' in info['continuations']


def test_candidate_moves_multiple_targets():
    trie = load_book()
    res = query_db.candidate_moves_for_position(
        trie,
        ['Hyperaccelerated Dragon', 'Italian Game', 'Scandinavian'],
        ['e2e4']
    )
    assert {'c7c5', 'd7d5', 'g7g6'} <= set(res.keys())
    assert res['d7d5']['queried'] == ['Scandinavian']
    assert res['c7c5']['queried'] == ['Hyperaccelerated Dragon']
    assert res['g7g6']['queried'] == ['Hyperaccelerated Dragon']