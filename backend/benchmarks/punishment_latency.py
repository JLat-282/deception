from __future__ import annotations

import argparse
from collections import Counter
from statistics import median
from time import perf_counter

from backend.app.difficulty import build_blueprint, public_presets


def percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * proportion))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure punishment blueprint scheduling and validation."
    )
    parser.add_argument("--samples", type=int, default=10_000)
    parser.add_argument("--enforce-target", action="store_true")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be at least 1")

    passed = True
    print(f"Punishment blueprint latency ({args.samples} total samples)")
    per_preset = max(1, args.samples // len(public_presets()))
    for preset in public_presets():
        timings: list[float] = []
        occurrences: Counter[str] = Counter()
        event_occurrences: Counter[str] = Counter()
        for index in range(per_preset):
            started = perf_counter()
            blueprint = build_blueprint(
                preset.key, f"punishment-benchmark:{preset.key}:{index}"
            )
            timings.append((perf_counter() - started) * 1_000)
            occurrences.update({plan.kind for plan in blueprint.punishment_plans})
            event_occurrences.update(
                plan.kind for plan in blueprint.punishment_plans
            )
        p50 = median(timings)
        p95 = percentile(timings, 0.95)
        p99 = percentile(timings, 0.99)
        maximum = max(timings)
        p999 = percentile(timings, 0.999)
        p99_limit = 10.0 if preset.key == "deception@3" else 5.0
        hard_limit = 20.0 if preset.key == "deception@3" else 10.0
        passed = (
            passed
            and p99 <= p99_limit
            and p999 <= hard_limit
        )
        rates = ", ".join(
            f"{kind}={count / per_preset:.1%}"
            for kind, count in sorted(occurrences.items())
        )
        print(
            f"- {preset.key}: p50={p50:.3f}ms p95={p95:.3f}ms "
            f"p99={p99:.3f}ms p99.9={p999:.3f}ms max={maximum:.3f}ms "
            f"p99Budget={p99_limit:.0f}ms p99.9Ceiling={hard_limit:.0f}ms"
        )
        print(f"  encounters: {rates or 'none'}")
        if preset.intrusion_probability:
            intrusion_per_row = (
                event_occurrences["intrusion"] / (per_preset * 4)
            )
            print(
                "  intrusion per eligible row: "
                f"{intrusion_per_row:.1%}"
            )

    if args.enforce_target and not passed:
        print("Target missed: punishment scheduling exceeded its latency budget.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
