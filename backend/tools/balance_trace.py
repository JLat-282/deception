from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.deception import DeceptionEngine, VisibleGuess
from backend.app.difficulty import build_blueprint, get_preset
from backend.app.engine import TruthEngine, load_word_list, normalize_word


def full_engine() -> TruthEngine:
    data_dir = Path(__file__).resolve().parents[1] / "app" / "data"
    return TruthEngine(
        load_word_list(data_dir / "words"),
        load_word_list(data_dir / "answers"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trace one deterministic blueprint and its lie decisions."
    )
    parser.add_argument("--preset", default="doubt-2@3")
    parser.add_argument("--seed", default="trace")
    parser.add_argument("--answer", required=True)
    parser.add_argument(
        "--guess", action="append", default=[],
        help="Guess in play order. Repeat the flag for multiple rows.",
    )
    args = parser.parse_args()

    engine = full_engine()
    answer = normalize_word(args.answer)
    if answer not in engine.answers:
        parser.error("--answer must be in the curated answer list")
    blueprint = build_blueprint(args.preset, args.seed)
    preset = get_preset(args.preset)
    deception = DeceptionEngine(engine)
    history: list[VisibleGuess] = []
    decisions: list[dict[str, object]] = []
    for attempt, raw_guess in enumerate(args.guess, start=1):
        guess = engine.validate_guess(raw_guess)
        truth = engine.evaluate(guess, answer)
        displayed = truth
        diagnostics: dict[str, object] = {
            "reason": "notScheduled",
        }
        if (
            attempt in blueprint.lie_attempts
            and attempt < 6
            and guess != answer
        ):
            decision = deception.choose_feedback(
                guess=guess,
                real_answer=answer,
                truth_feedback=truth,
                prior_history=history,
                seed=f"{blueprint.seed}:{attempt}",
                max_false_tiles=blueprint.false_tiles_for_attempt(attempt),
                credible_lie_row_cap=preset.lie_policy.credible_lie_row_cap,
                repeat_thread_probability=(
                    preset.lie_policy.repeat_thread_probability
                ),
                time_budget_ms=40,
            )
            displayed = decision.feedback
            diagnostics = decision.diagnostics()
        decisions.append(
            {
                "attempt": attempt,
                "guess": guess,
                "truth": truth,
                "displayed": displayed,
                "diagnostics": diagnostics,
            }
        )
        history.append(VisibleGuess(guess, displayed))
        if guess == answer:
            break

    print(
        json.dumps(
            {
                "preset": blueprint.preset_key,
                "schemaVersion": blueprint.schema_version,
                "lieAttempts": blueprint.lie_attempts,
                "lieTileCounts": blueprint.lie_tile_counts,
                "punishments": [
                    {
                        "kind": plan.kind,
                        "triggerAttempt": plan.trigger_attempt,
                        "effectiveAttempt": plan.effective_attempt,
                        "config": plan.config,
                    }
                    for plan in blueprint.punishment_plans
                ],
                "decisions": decisions,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
