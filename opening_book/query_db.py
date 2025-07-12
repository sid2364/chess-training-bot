import json
import re
from typing import List, Tuple, Dict, Any, Set, Optional


def load_trie(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def find_matching_nodes(
    node: dict,
    targets: List[str]
) -> List[Tuple[List[str], dict, Set[str]]]:
    # Return (path, node, matched_targets), where matched_targets is the subset of `targets` whose substrings matched node['opening_name']
    out: List[Tuple[List[str], dict, Set[str]]] = []
    patterns = [(t, re.compile(re.escape(t), re.IGNORECASE))
                for t in targets]

    def dfs(n: dict, path: List[str]):
        name = n.get('opening_name') or ""
        matched = {t for t, p in patterns if p.search(name)}
        if matched:
            out.append((path.copy(), n, matched))
        for uci, child in n.get('children', {}).items():
            path.append(uci)
            dfs(child, path)
            path.pop()

    dfs(node, [])
    return out

def collect_full_continuations(path: List[str], node: dict) -> List[List[str]]:
    if not node.get('children'):
        return [path]
    leaves: List[List[str]] = []
    def dfs(n: dict, so_far: List[str]):
        if not n.get('children'):
            leaves.append(so_far.copy())
        else:
            for uci, ch in n['children'].items():
                so_far.append(uci)
                dfs(ch, so_far)
                so_far.pop()
    dfs(node, path.copy())
    return leaves

def get_node_by_path(trie: dict, path: List[str]) -> dict:
    n = trie
    for move in path:
        n = n.get('children', {}).get(move, {})
    return n

def candidate_moves_for_position(
    trie: dict,
    targets: List[str],
    current_seq: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Returns a mapping:
      {
      "c7c5": {
        "stats": [  179913, 240745, 147001 ],
        "continuations": [
          "e2e4 c7c5 g1f3 g7g6 d2d4",
          "e2e4 c7c5 g1f3 g7g6"
        ]
      },
      "g7g6": {
        "stats": [  3569, 3655, 2340 ],
        "continuations": [
          "e2e4 g7g6 g1f3 c7c5 d2d4",
          "e2e4 g7g6 g1f3 c7c5"
        ]
      },
      # ... etc. for any other transposed paths
    }
    """
    matches = find_matching_nodes(trie, targets)

    all_conts: List[Tuple[List[str], Set[str]]] = []
    # build list of (full_continuation_path, matched_targets)
    for path, node, matched in matches:
        for leaf in collect_full_continuations(path, node):
            all_conts.append((leaf, matched))

    k = len(current_seq)
    resp: Dict[str, Dict[str, Any]] = {}

    for cont, matched in all_conts:
        for i in range(len(cont) - k):
            if cont[i:i+k] == current_seq:
                nxt = cont[i+k]
                full_path = cont[:i+k+1]
                child = get_node_by_path(trie, full_path)
                stats = child.get('stats')
                entry = resp.setdefault(nxt, {
                    'stats': stats,
                    'continuations': [],
                    'queried': set()
                })
                # record only those targets that actually matched here
                entry['queried'].update(matched)
                line = " ".join(cont)
                if line not in entry['continuations']:
                    entry['continuations'].append(line)

    # convert queried sets to sorted lists
    for info in resp.values():
        info['queried'] = sorted(info['queried'])

    return resp

def get_opening_for_moves(trie: dict, moves: list[str]) -> Optional[str]:
    """
    Follow `moves` down the trie via get_node_by_path.
    If *any* move isn’t in the book, return None.
    Otherwise return the deepest non-null opening_name seen.
    """
    last_name: Optional[str] = None
    for i in range(1, len(moves) + 1):
        prefix = moves[:i]
        node = get_node_by_path(trie, prefix)  # must exist, since full path did
        if node.get("opening_name"):
            last_name = node["opening_name"]

    return last_name

if __name__ == "__main__":
    # Testing to see all the variations of "Hyperaccelerated Dragon", "Italian Game", "Scandinavian" when current move is "e2e4"
    # book = load_trie("opening_book.json")
    # cands = candidate_moves_for_position(
    #     trie=book,
    #     targets=["Hyperaccelerated Dragon", "Italian Game", "Scandinavian"],
    #     current_seq=["e2e4"]
    # )
    # # print(cands)
    # for move, info in cands.items():
    #     print(f"--> {move}")
    #     print(f"\tstats:\t\t{info['stats']}")
    #     print(f"\tqueried:\t\t{info['queried']}")
    #     print("\toccurs in:")
    #     for line in info['continuations']:
    #         print("\t\t\t", line)
    #

    # Query the local DB to see what opening we are currently in
    with open("opening_book.json", encoding="utf-8") as f:
        trie = json.load(f)

    moves = "e2e4 g7g6 g1f3 c7c5 d2d4 f8g7 c2c4".split()
    print(get_opening_for_moves(trie, moves))