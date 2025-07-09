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
DEPTH = 6
TOP_N = 8
MIN_GAMES = 100
OPENING_BOOK_FILE = "opening_book.json"


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
    return response.json().get('moves', [])


def crawl(node: Node, board: chess.Board, ply: int, max_ply: int, top_n: int,
          min_games: int, cache: Dict[Tuple[Optional[str], int], list]) -> None:
    if ply >= max_ply:
        return

    play = ','.join(m.uci() for m in board.move_stack) if board.move_stack else None
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

        if uci not in node.children:
            node.children[uci] = Node()
        child = node.children[uci]
        child.stats = stats
        child.opening_name = opening_name
        child.eco = eco

        board.push_uci(uci)
        crawl(child, board, ply + 1, max_ply, top_n, min_games, cache)
        board.pop()


def save_trie(root: Node, output_path: str) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(root.to_dict(), f, ensure_ascii=False, indent=2)
    logger.info(f'Trie saved to {output_path}')


def load_trie(input_path: str) -> Node:
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return Node.from_dict(data)


def main():
    # Load existing trie if present, else start fresh
    if os.path.exists(OPENING_BOOK_FILE):
        logger.info(f'Loading existing trie from {OPENING_BOOK_FILE}')
        root = load_trie(OPENING_BOOK_FILE)
    else:
        root = Node()

    logger.info(f'Configured to crawl up to depth={DEPTH}, top_n={TOP_N}')

    # Compute the deepest level already built
    def current_depth(node: Node) -> int:
        if not node.children:
            return 0
        return 1 + max(current_depth(child) for child in node.children.values())

    existing = current_depth(root)
    logger.info(f'Existing trie reaches depth={existing}')

    board = chess.Board()
    cache: Dict[Tuple[Optional[str], int], list] = {}

    if existing < DEPTH:
        logger.info(f'Resuming crawl from depth {existing} to {DEPTH}')

        # Traverse to each frontier node and resume crawling there
        def resume(node: Node, board: chess.Board, ply: int):
            if ply == existing:
                crawl(node, board, ply, max_ply=DEPTH, top_n=TOP_N, min_games=MIN_GAMES, cache=cache)
            else:
                for uci, child in node.children.items():
                    board.push_uci(uci)
                    resume(child, board, ply + 1)
                    board.pop()

        resume(root, board, 0)
    else:
        logger.info('Nothing to do—already at or beyond desired depth')

    save_trie(root, OPENING_BOOK_FILE)


if __name__ == '__main__':
    main()
