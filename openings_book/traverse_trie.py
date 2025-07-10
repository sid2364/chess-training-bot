import json
import sys
import os

# ``traverse_trie`` can be run as a script, so use an absolute import to load
# constants from ``crawler`` regardless of how this module is executed.  When
# executed directly the parent directory is added to ``sys.path`` so the package
# can be resolved.
if __package__ is None or __package__ == "":
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from openings_book.crawler import OPENING_BOOK_FILE  # "opening_book.json"


def traverse(node: dict, move_sequence: list[str], depth: int) -> None:
    opening_name = node.get('opening_name')
    if opening_name:
        moves_san = ' '.join(move_sequence)
        indent = '  ' * depth
        print(f"{indent}{moves_san} - {opening_name}")

    for uci, child in node.get('children', {}).items():
        traverse(child, move_sequence + [uci], depth + 1)


def main(json_path: str) -> None:
    # Load the serialized trie
    with open(json_path, 'r', encoding='utf-8') as f:
        trie = json.load(f)

    # Start traversal from the root; empty move sequence and depth 0
    traverse(trie, [], 0)


if __name__ == '__main__':
    main(OPENING_BOOK_FILE)
