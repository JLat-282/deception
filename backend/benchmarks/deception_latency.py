from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from time import perf_counter

from backend.app.deception import DeceptionEngine, VisibleGuess
from backend.app.engine import TruthEngine, load_word_list


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"


@dataclass(frozen=True)
class Scenario:
    name: str
    guess: str
    prior_guesses: tuple[str, ...]
    baseline_p50_ms: float | None
    answer: str = "crane"
    maximum_p99_ms: float | None = None
    must_activate: bool = False


SCENARIOS = (
    Scenario("first selected row", "slate", (), 18.94),
    Scenario("selected row after one guess", "fight", ("slate",), 35.61),
    Scenario(
        "selected row after four guesses",
        "shack",
        ("slate", "fight", "mould", "berry"),
        30.11,
    ),
    Scenario(
        name="constraint-backed fallback",
        guess="picky",
        prior_guesses=("stare", "cloud"),
        baseline_p50_ms=None,
        answer="gnash",
        maximum_p99_ms=100,
        must_activate=True,
    ),
)


def percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * proportion))
    return ordered[index]


def benchmark_scenario(
    truth_engine: TruthEngine,
    deception_engine: DeceptionEngine,
    scenario: Scenario,
    samples: int,
) -> dict[str, float]:
    answer = scenario.answer
    history = tuple(
        VisibleGuess(
            guess=guess,
            feedback=truth_engine.evaluate(guess, answer),
        )
        for guess in scenario.prior_guesses
    )
    truth_feedback = truth_engine.evaluate(scenario.guess, answer)
    timings: list[float] = []

    for sample in range(samples):
        started_at = perf_counter()
        decision = deception_engine.choose_feedback(
            guess=scenario.guess,
            real_answer=answer,
            truth_feedback=truth_feedback,
            prior_history=history,
            seed=f"benchmark-{scenario.name}-{sample}",
        )
        timings.append((perf_counter() - started_at) * 1_000)
        if scenario.must_activate and not decision.activated:
            raise RuntimeError(
                f"{scenario.name} did not activate its expected lie"
            )

    return {
        "p50": median(timings),
        "p95": percentile(timings, 0.95),
        "p99": percentile(timings, 0.99),
        "max": max(timings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure the deception planner's cold calculation path."
    )
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument(
        "--enforce-target",
        action="store_true",
        help=(
            "Fail unless optimized scenarios remain at least 40% faster "
            "than baseline and budgeted scenarios remain within budget."
        ),
    )
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be at least 1")

    truth_engine = TruthEngine(
        load_word_list(DATA_DIR / "words"),
        load_word_list(DATA_DIR / "answers"),
    )
    deception_engine = DeceptionEngine(truth_engine)
    target_met = True

    print(f"Deception planner latency ({args.samples} samples per scenario)")
    for scenario in SCENARIOS:
        results = benchmark_scenario(
            truth_engine,
            deception_engine,
            scenario,
            args.samples,
        )
        metrics = "  ".join(
            f"{name}={value:.2f}ms" for name, value in results.items()
        )
        if scenario.baseline_p50_ms is not None:
            reduction = (
                1 - results["p50"] / scenario.baseline_p50_ms
            ) * 100
            scenario_met = reduction >= 40
            summary = f"p50 reduction={reduction:.1f}%"
        elif scenario.maximum_p99_ms is not None:
            scenario_met = results["p99"] <= scenario.maximum_p99_ms
            summary = f"p99 budget={scenario.maximum_p99_ms:.0f}ms"
        else:
            scenario_met = True
            summary = ""
        target_met = target_met and scenario_met
        print(f"- {scenario.name}: {metrics}  {summary}".rstrip())

    if args.enforce_target and not target_met:
        print("Target missed: a performance requirement was not met.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
