from dataclasses import dataclass, field
from typing import List

# Default opening lists used for interactive setup and filtering
white_openings = [
    "e4 - King's Pawn Game",
    "d4 - Queen's Pawn Game",
    "c4 - English Opening",
    "d4 d5 c4 - Queen's Gambit",
    "d4 d5 Bf4 - Queen's Pawn Game: Accelerated London System",
    "e4 e5 Nc3 - Vienna Game",
    "e4 e5 f4 - King's Gambit",
]

black_openings = [
    "e4 e5 - King's Pawn Game",
    "e4 c5 - Sicilian Defense",
    "e4 d5 - Scandinavian Defense",
    "e4 e6 - French Defense",
    "e4 d6 - Pirc Defense",
    "e4 c6 - Caro-Kann Defense",
    "d4 Nf6 - Indian Defense",
    "d4 g6 - Queen's Pawn Game: Modern Defense",
]

@dataclass
class BotProfile:
    chosen_white: List[str] = field(default_factory=list)
    chosen_black: List[str] = field(default_factory=list)
    our_color: bool = True  # True = White, False = Black
    opp_rating: int = 1500
    challenge_rating: int = 1500
    challenge: int = 100

    def get_openings_choice_from_user(self) -> None:
        def choose(options: List[str], color_name: str) -> List[str]:
            while True:
                print(f"Select your {color_name} openings by number (comma-separated):")
                print("  0. No preference")
                for idx, opening in enumerate(options, start=1):
                    print(f"  {idx}. {opening}")
                user_input = input(f"Your {color_name} choices: ").strip()

                # default or explicit no preference
                if user_input == "" or user_input == "0":
                    return options[:3]

                # parse comma-separated ints
                try:
                    picks = [int(tok) for tok in user_input.split(",") if tok.strip()]
                except ValueError:
                    print(" -> Please enter only numbers, separated by commas.")
                    continue

                if any(p < 0 or p > len(options) for p in picks):
                    print(f" -> Each number must be between 0 and {len(options)}.")
                    continue

                if 0 in picks:
                    return options[:3]

                seen = set()
                selection = []
                for p in picks:
                    if p not in seen:
                        seen.add(p)
                        selection.append(options[p - 1])
                return selection

        self.chosen_white = choose(white_openings, "White")
        self.chosen_black = choose(black_openings, "Black")

        while True:
            user_input = input("Relative to your ELO, what should the BOT's ELO be? (+/- 100): ").strip()
            if user_input in ("", "0"):
                self.challenge = 0
                break
            try:
                self.challenge = int(user_input)
                break
            except ValueError:
                print(" -> Please enter a valid integer.")
                continue

    def determine_color_and_opp_rating(self, start: dict) -> None:
        white_player = start["white"]
        black_player = start["black"]

        from .trainer import OUR_NAME  # local import to avoid circular import
        import chess

        if white_player["id"] == OUR_NAME:
            self.our_color = chess.WHITE
            self.opp_rating = black_player["rating"]
        else:
            self.our_color = chess.BLACK
            self.opp_rating = white_player["rating"]
        self.challenge_rating = self.opp_rating + self.challenge

    @staticmethod
    def strip_opening_name(opening: str) -> str:
        if "-" not in opening:
            return opening
        return opening.split("-", 1)[1].strip()

    def get_clean_openings(self) -> tuple[List[str], List[str]]:
        return (
            [self.strip_opening_name(o) for o in self.chosen_white],
            [self.strip_opening_name(o) for o in self.chosen_black],
        )
