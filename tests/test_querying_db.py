import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from opening_book import query_db

BOOK_PATH = os.path.join(os.path.dirname(__file__), "..", "opening_book.json") # kinda depends on there being a .json already?


def load_book():
    return query_db.load_trie(BOOK_PATH)


def test_load_trie_has_children():
    trie = load_book()
    assert trie.get('children')


def _sample_openings(trie, n=2):
    samples = []

    def dfs(node, path):
        if len(samples) >= n:
            return
        if node.get('opening_name'):
            samples.append((path.copy(), node))
        for uci, child in node.get('children', {}).items():
            path.append(uci)
            dfs(child, path)
            path.pop()

    dfs(trie, [])
    return samples


def test_get_node_by_path():
    trie = load_book()
    (path, node) = _sample_openings(trie, 1)[0]
    fetched = query_db.get_node_by_path(trie, path)
    assert fetched.get('opening_name') == node.get('opening_name')
    assert fetched.get('stats') == node.get('stats')


def test_find_matching_nodes_path_exists():
    trie = load_book()
    (path, node) = _sample_openings(trie, 1)[0]
    keyword = node['opening_name'].split()[0]
    matches = query_db.find_matching_nodes(trie, [keyword])
    assert any(p == path for p, _, _ in matches)


def test_collect_full_continuations():
    trie = load_book()
    # pick a node with children
    samples = [s for s in _sample_openings(trie, 5) if s[1].get('children')]
    if not samples:
        samples = _sample_openings(trie, 1)
    path, node = samples[0]
    leaves = query_db.collect_full_continuations(path, node)
    assert leaves
    assert all(seq[: len(path)] == path for seq in leaves)
    for seq in leaves:
        n = query_db.get_node_by_path(trie, seq)
        assert not n.get('children')


def test_candidate_moves_for_sample_opening():
    trie = load_book()
    (path, node) = _sample_openings(trie, 1)[0]
    if len(path) < 1:
        return
    target = node['opening_name']
    prefix = path[:-1]
    res = query_db.candidate_moves_for_position(trie, [target], prefix)
    assert path[-1] in res
    info = res[path[-1]]
    assert isinstance(info.get('stats'), list) and len(info['stats']) == 3
    assert target in info['queried']
    assert any(
        cont.split()[: len(prefix) + 1] == prefix + [path[-1]]
        for cont in info['continuations']
    )

def test_candidate_moves_multiple_targets():
    trie = load_book()
    samples = _sample_openings(trie, 2)
    targets = [node['opening_name'] for _, node in samples]
    res = query_db.candidate_moves_for_position(trie, targets, [])
    assert res
    for target in targets:
        assert any(target in info['queried'] for info in res.values())

def test_choose_book_move_returns_candidate():
    trie = load_book()
    seq = "e2e4 c7c5 g1f3".split()
    move = query_db.choose_book_move(trie, ["Hyperaccelerated"], seq)
    cands = query_db.candidate_moves_for_position(trie, ["Hyperaccelerated"], seq)
    assert move is None or move in cands