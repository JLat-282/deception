from __future__ import annotations

import pytest

from backend.app.engine import TruthEngine, check_guess, make_feedback, normalize_word
from backend.app.errors import GuessValidationError


def test_normalize_word_strips_and_lowercases() -> None:
    assert normalize_word("  CrAnE ") == "crane"


def test_all_green() -> None:
    assert check_guess("crane", "crane") == (
        "green",
        "green",
        "green",
        "green",
        "green",
    )


def test_normal_mixed_colors() -> None:
    assert check_guess("slate", "crane") == (
        "gray",
        "gray",
        "green",
        "gray",
        "green",
    )


def test_repeated_guess_letter_is_not_overcounted() -> None:
    assert check_guess("eerie", "crane") == (
        "gray",
        "gray",
        "yellow",
        "gray",
        "green",
    )


def test_repeated_answer_letter_can_be_used_twice() -> None:
    assert check_guess("allay", "llama") == (
        "yellow",
        "green",
        "yellow",
        "yellow",
        "gray",
    )


def test_feedback_serialization() -> None:
    assert make_feedback(("green", "yellow", "gray", "gray", "green")) == "GYBBG"


def test_truth_engine_validates_length_and_dictionary() -> None:
    engine = TruthEngine(
        valid_guesses=("crane", "slate"),
        answers=("crane",),
    )

    with pytest.raises(GuessValidationError) as short:
        engine.validate_guess("cat")
    assert short.value.code == "INVALID_LENGTH"

    with pytest.raises(GuessValidationError) as unknown:
        engine.validate_guess("zzzzz")
    assert unknown.value.code == "INVALID_WORD"

    assert engine.validate_guess(" SLATE ") == "slate"


def test_answers_must_be_valid_guesses() -> None:
    with pytest.raises(ValueError, match="Answers must also be valid guesses"):
        TruthEngine(valid_guesses=("slate",), answers=("crane",))
