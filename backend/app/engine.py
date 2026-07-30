from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Iterable

from .errors import GuessValidationError


WORD_LENGTH = 5
MAX_GUESSES = 6
WORD_PATTERN = re.compile(r"^[a-z]{5}$")


def normalize_word(raw_word: str) -> str:
    return raw_word.strip().lower()


def load_word_list(path: Path) -> tuple[str, ...]:
    seen: set[str] = set()
    words: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        word = normalize_word(raw_line)
        if WORD_PATTERN.fullmatch(word) and word not in seen:
            seen.add(word)
            words.append(word)
    if not words:
        raise ValueError(f"No five-letter words found in {path}.")
    return tuple(words)


def check_guess(guess: str, answer: str) -> tuple[str, ...]:
    """Return truthful color names with standard duplicate-letter accounting."""

    result = ["gray"] * WORD_LENGTH
    remaining = Counter()

    for index, (guessed_letter, answer_letter) in enumerate(zip(guess, answer)):
        if guessed_letter == answer_letter:
            result[index] = "green"
        else:
            remaining[answer_letter] += 1

    for index, guessed_letter in enumerate(guess):
        if result[index] == "green":
            continue
        if remaining[guessed_letter] > 0:
            result[index] = "yellow"
            remaining[guessed_letter] -= 1

    return tuple(result)


def make_feedback(colors: Iterable[str]) -> str:
    marker_for_color = {"green": "G", "yellow": "Y", "gray": "B"}
    return "".join(marker_for_color[color] for color in colors)


class TruthEngine:
    def __init__(
        self, valid_guesses: Iterable[str], answers: Iterable[str]
    ) -> None:
        self.valid_guesses = frozenset(valid_guesses)
        self.answers = tuple(answers)

        if not self.answers:
            raise ValueError("At least one answer is required.")
        missing_answers = set(self.answers) - self.valid_guesses
        if missing_answers:
            sample = ", ".join(sorted(missing_answers)[:3])
            raise ValueError(f"Answers must also be valid guesses: {sample}")

    def validate_guess(self, raw_guess: str) -> str:
        guess = normalize_word(raw_guess)
        if len(guess) != WORD_LENGTH:
            raise GuessValidationError(
                "INVALID_LENGTH", f"Enter exactly {WORD_LENGTH} letters."
            )
        if not WORD_PATTERN.fullmatch(guess) or guess not in self.valid_guesses:
            raise GuessValidationError(
                "INVALID_WORD", "That word is not in the accepted word list."
            )
        return guess

    def evaluate(self, guess: str, answer: str) -> str:
        # The deception planner evaluates a guess against the full answer
        # corpus. Build its marker string directly so that hot path does not
        # allocate a Counter, a tuple of color names, and a second mapping
        # pass for every possible answer.
        result = ["B", "B", "B", "B", "B"]
        remaining: dict[str, int] = {}

        for index in range(WORD_LENGTH):
            guessed_letter = guess[index]
            answer_letter = answer[index]
            if guessed_letter == answer_letter:
                result[index] = "G"
            else:
                remaining[answer_letter] = (
                    remaining.get(answer_letter, 0) + 1
                )

        for index in range(WORD_LENGTH):
            if result[index] == "G":
                continue
            guessed_letter = guess[index]
            count = remaining.get(guessed_letter, 0)
            if count:
                result[index] = "Y"
                remaining[guessed_letter] = count - 1

        return "".join(result)
