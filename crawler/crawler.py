import os
import time
import json
import requests
import chess
import logging
from typing import Dict, Tuple, Optional

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

logger = logging.getLogger(__name__)
SLEEP_TIME = 30

EXPLORER_URL = "https://explorer.lichess.ovh/masters"

DEPTH = 5
TOP_N = 8
MIN_GAMES = 100
OUTPUT_PATH = "opening_book.json"


class Node:
    # A node in the opening-book trie. Used to create the database JSON
    def __init__(self):
        self.children: Dict[str, 'Node'] = {}
        self.stats: Optional[Tuple[int, int, int]] = None
        self.opening_name: Optional[str] = None
        self.eco: Optional[str] = None

    def to_dict(self) -> Dict:
        # Recursively convert trie to a serializable dict
        return {
            'stats': self.stats,
            'opening_name': self.opening_name,
            'eco': self.eco,
            'children': {uci: node.to_dict() for uci, node in self.children.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Node':
        # Reconstruct Node from serialized dict
        node = cls()
        node.stats = tuple(data.get('stats')) if data.get('stats') is not None else None
        node.opening_name = data.get('opening_name')
        node.eco = data.get('eco')
        for uci, child_data in data.get('children', {}).items():
            node.children[uci] = cls.from_dict(child_data)
        return node


def fetch_book_moves(play: Optional[str], top_n: int) -> list:
    # Query the Lichess Explorer url for top continuations using the 'play' parameter
    # Also retries once after 60s on HTTP 429.
    params = {}
    if play:
        params['play'] = play
    params['moves'] = top_n

    response = requests.get(EXPLORER_URL, params=params)
    if response.status_code == 429:
        logger.warning(f'Rate limit hit, sleeping {SLEEP_TIME}s and retrying')
        time.sleep(SLEEP_TIME)
        response = requests.get(EXPLORER_URL, params=params)
    response.raise_for_status()
    data = response.json()
    return data.get('moves', [])


def crawl(node: Node, board: chess.Board, ply: int, max_ply: int, top_n: int,
          min_games: int, cache: Dict[str, list]) -> None:
    # Recursively build the opening trie up to max_ply using 'play', prune branches with total games < min_games
    # Uses cache to avoid duplicate queries by 'play'
    if ply >= max_ply:
        return

    play = ','.join(m.uci() for m in board.move_stack) if board.move_stack else None

    # Use cache to avoid refetch
    cache_key = (play, top_n)
    if cache_key in cache:
        moves = cache[cache_key]
        logger.debug(f'Cache hit for play: {play}')
    else:
        logger.info(f'Fetching ply {ply}, play: {play}')
        moves = fetch_book_moves(play, top_n)
        cache[cache_key] = moves

    for m in moves:
        total = m.get('white', 0) + m.get('draws', 0) + m.get('black', 0)
        if total < min_games:
            continue
        uci = m['uci']
        stats = (m.get('white', 0), m.get('draws', 0), m.get('black', 0))
        opening = m.get('opening') or {}
        opening_name = opening.get('name')
        eco = opening.get('eco')

        # Add or update node
        if uci not in node.children:
            node.children[uci] = Node()
        child = node.children[uci]
        child.stats = stats
        child.opening_name = opening_name
        child.eco = eco

        # Recurse deeper
        board.push_uci(uci)
        crawl(child, board, ply + 1, max_ply, top_n, min_games, cache)
        board.pop()


def save_trie(root: Node, output_path: str) -> None:
    # Serialize the trie to JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(root.to_dict(), f, ensure_ascii=False, indent=2)
    logger.info(f'Trie saved to {output_path}')


def load_trie(input_path: str) -> Node:
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return Node.from_dict(data)

def main():
    # Always start fresh
    root = Node()

    board = chess.Board()
    cache: Dict[tuple, list] = {}
    crawl(root, board, ply=0,
          max_ply=DEPTH,
          top_n=TOP_N,
          min_games=MIN_GAMES,
          cache=cache)

    save_trie(root, OUTPUT_PATH)

if __name__ == '__main__':
    main()
