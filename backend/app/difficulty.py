from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
from types import MappingProxyType
from typing import Literal, Mapping


DEFAULT_PRESET_KEY = "doubt-2@1"


@dataclass(frozen=True)
class PresetDefinition:
    key: str
    name: str
    order: int
    pressure: str
    description: str
    available: bool
    lie_count_weights: tuple[tuple[int, float], ...]
    max_false_tiles: int
    two_tile_probability: float
    false_victory_probability: float
    timer_count_weights: tuple[tuple[int, float], ...]
    timer_duration_weights: tuple[tuple[int, float], ...]
    reverse_fallback_probability: float
    max_reverse_events: int
    blackout_probability: float
    max_blackout_events: int
    blackout_reserves_next_attempt: bool
    combination_policy: Literal["none", "limited", "broad"]


PRESETS: Mapping[str, PresetDefinition] = MappingProxyType(
    {
        "doubt-1@1": PresetDefinition(
            key="doubt-1@1",
            name="Doubt I",
            order=1,
            pressure="Low",
            description="An approachable introduction to uncertain feedback.",
            available=True,
            lie_count_weights=((1, 1.0),),
            max_false_tiles=1,
            two_tile_probability=0.0,
            false_victory_probability=0.0,
            timer_count_weights=((0, 0.75), (1, 0.25)),
            timer_duration_weights=((30, 1.0),),
            reverse_fallback_probability=0.05,
            max_reverse_events=1,
            blackout_probability=0.0,
            max_blackout_events=0,
            blackout_reserves_next_attempt=False,
            combination_policy="none",
        ),
        "doubt-2@1": PresetDefinition(
            key="doubt-2@1",
            name="Doubt II",
            order=2,
            pressure="Standard",
            description="The complete standard Deception experience.",
            available=True,
            lie_count_weights=((1, 0.20), (2, 0.80)),
            max_false_tiles=1,
            two_tile_probability=0.0,
            false_victory_probability=0.0,
            timer_count_weights=((0, 0.55), (1, 0.45)),
            timer_duration_weights=((30, 0.70), (10, 0.30)),
            reverse_fallback_probability=0.10,
            max_reverse_events=1,
            blackout_probability=0.20,
            max_blackout_events=1,
            blackout_reserves_next_attempt=True,
            combination_policy="none",
        ),
        "doubt-3@1": PresetDefinition(
            key="doubt-3@1",
            name="Doubt III",
            order=3,
            pressure="High",
            description="Aggressive pressure with repeated punishments.",
            available=True,
            lie_count_weights=((2, 0.40), (3, 0.60)),
            max_false_tiles=2,
            two_tile_probability=0.25,
            false_victory_probability=0.0,
            timer_count_weights=((0, 0.15), (1, 0.55), (2, 0.30)),
            timer_duration_weights=((30, 0.50), (10, 0.50)),
            reverse_fallback_probability=0.20,
            max_reverse_events=2,
            blackout_probability=0.45,
            max_blackout_events=1,
            blackout_reserves_next_attempt=False,
            combination_policy="limited",
        ),
        "deception@1": PresetDefinition(
            key="deception@1",
            name="Deception",
            order=4,
            pressure="Extreme",
            description="An expert survival challenge.",
            available=True,
            lie_count_weights=((3, 0.15), (4, 0.35), (5, 0.50)),
            max_false_tiles=2,
            two_tile_probability=0.50,
            false_victory_probability=0.05,
            timer_count_weights=((1, 0.25), (2, 0.45), (3, 0.30)),
            timer_duration_weights=((30, 0.30), (10, 0.70)),
            reverse_fallback_probability=0.35,
            max_reverse_events=3,
            blackout_probability=0.80,
            max_blackout_events=1,
            blackout_reserves_next_attempt=False,
            combination_policy="broad",
        ),
    }
)


def validate_presets() -> None:
    presets = tuple(PRESETS.values())
    if len({preset.key for preset in presets}) != len(presets):
        raise ValueError("Difficulty preset keys must be unique.")
    if len({preset.order for preset in presets}) != len(presets):
        raise ValueError("Difficulty preset ranks must be unique.")
    for mapping_key, preset in PRESETS.items():
        if mapping_key != preset.key:
            raise ValueError(f"Preset registry key does not match definition: {mapping_key}")
        if not preset.key.endswith("@1"):
            raise ValueError(f"Preset key must be versioned: {preset.key}")
        for weights in (
            preset.lie_count_weights,
            preset.timer_count_weights,
            preset.timer_duration_weights,
        ):
            if not weights or len({choice for choice, _ in weights}) != len(weights):
                raise ValueError(f"Preset choices must be non-empty and unique: {preset.key}")
            if any(weight < 0 for _, weight in weights):
                raise ValueError(f"Preset weights cannot be negative: {preset.key}")
            if abs(sum(weight for _, weight in weights) - 1.0) > 1e-9:
                raise ValueError(f"Preset weights must total 1: {preset.key}")
        for probability in (
            preset.two_tile_probability,
            preset.false_victory_probability,
            preset.reverse_fallback_probability,
            preset.blackout_probability,
        ):
            if not 0 <= probability <= 1:
                raise ValueError(f"Preset probability is invalid: {preset.key}")


validate_presets()


@dataclass(frozen=True)
class BlueprintOverrides:
    lie_attempts: tuple[int, ...] | None = None
    lie_tile_counts: tuple[int, ...] | None = None
    timer_roll: float | None = None
    timer_attempt: int | None = None
    timer_duration: int | None = None
    timer_attempts: tuple[int, ...] | None = None
    timer_durations: tuple[int, ...] | None = None
    blackout_roll: float | None = None
    blackout_attempt: int | None = None
    false_victory_enabled: bool | None = None
    timer_enabled: bool = True
    reverse_enabled: bool = True
    blackout_enabled: bool = True


@dataclass(frozen=True)
class TimerPlan:
    attempt: int
    duration_seconds: int


@dataclass(frozen=True)
class GameBlueprint:
    schema_version: int
    preset_key: str
    seed: str
    lie_attempts: tuple[int, ...]
    lie_tile_counts: tuple[int, ...]
    false_victory_enabled: bool
    timer_events: tuple[TimerPlan, ...]
    reverse_enabled: bool
    reverse_max_events: int
    reverse_seed: str
    reverse_fallback_probability: float
    blackout_attempt: int | None
    blackout_blocked_attempts: tuple[int, ...]

    @property
    def max_false_tiles(self) -> int:
        return max(self.lie_tile_counts, default=1)

    @property
    def timer_attempt(self) -> int | None:
        return self.timer_events[0].attempt if self.timer_events else None

    @property
    def timer_duration_seconds(self) -> int | None:
        return (
            self.timer_events[0].duration_seconds
            if self.timer_events
            else None
        )

    def false_tiles_for_attempt(self, attempt: int) -> int:
        try:
            return self.lie_tile_counts[self.lie_attempts.index(attempt)]
        except ValueError:
            return 1

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "GameBlueprint":
        value = json.loads(raw)
        schema_version = value.get("schema_version")
        if schema_version == 1:
            timer_events = ()
            if value.get("timer_attempt") is not None:
                timer_events = (
                    TimerPlan(
                        attempt=value["timer_attempt"],
                        duration_seconds=value["timer_duration_seconds"],
                    ),
                )
            return cls(
                schema_version=3,
                preset_key=value["preset_key"],
                seed=value["seed"],
                lie_attempts=tuple(value["lie_attempts"]),
                lie_tile_counts=tuple(1 for _ in value["lie_attempts"]),
                false_victory_enabled=False,
                timer_events=timer_events,
                reverse_enabled=value["reverse_enabled"],
                reverse_max_events=1,
                reverse_seed=value["reverse_seed"],
                reverse_fallback_probability=value[
                    "reverse_fallback_probability"
                ],
                blackout_attempt=value["blackout_attempt"],
                blackout_blocked_attempts=tuple(
                    value["blackout_blocked_attempts"]
                ),
            )
        if schema_version == 2:
            value["schema_version"] = 3
            value["false_victory_enabled"] = False
        elif schema_version != 3:
            raise ValueError(
                f"Unsupported game blueprint schema: {schema_version}"
            )
        value["lie_attempts"] = tuple(value["lie_attempts"])
        value["lie_tile_counts"] = tuple(value["lie_tile_counts"])
        value["timer_events"] = tuple(
            TimerPlan(**event) for event in value["timer_events"]
        )
        value["blackout_blocked_attempts"] = tuple(
            value["blackout_blocked_attempts"]
        )
        return cls(**value)


def get_preset(preset_key: str) -> PresetDefinition:
    try:
        return PRESETS[preset_key]
    except KeyError as error:
        raise ValueError(f"Unknown difficulty preset: {preset_key}") from error


def public_presets() -> tuple[PresetDefinition, ...]:
    return tuple(sorted(PRESETS.values(), key=lambda preset: preset.order))


def _number(seed: str, label: str) -> int:
    digest = hmac.new(
        seed.encode("utf-8"), label.encode("utf-8"), hashlib.sha256
    ).digest()
    return int.from_bytes(digest[:8], "big")


def _probability(seed: str, label: str) -> float:
    return _number(seed, label) / 2**64


def _weighted_choice(
    seed: str,
    label: str,
    choices: tuple[tuple[int, float], ...],
) -> int:
    roll = _probability(seed, label)
    cumulative = 0.0
    for value, weight in choices:
        cumulative += weight
        if roll < cumulative:
            return value
    return choices[-1][0]


def _weighted_choice_for_roll(
    roll: float, choices: tuple[tuple[int, float], ...]
) -> int:
    cumulative = 0.0
    for value, weight in choices:
        cumulative += weight
        if roll < cumulative:
            return value
    return choices[-1][0]


def _ranked_attempts(seed: str, label: str, attempts: range) -> list[int]:
    return sorted(attempts, key=lambda attempt: _number(seed, f"{label}:{attempt}"))


def build_blueprint(
    preset_key: str,
    seed: str,
    overrides: BlueprintOverrides = BlueprintOverrides(),
) -> GameBlueprint:
    """Build one deterministic, immutable game blueprint."""
    preset = get_preset(preset_key)
    if not preset.available:
        raise ValueError(f"Difficulty preset is not available: {preset_key}")

    lie_count = _weighted_choice(
        seed, "blueprint:v1:lie-count", preset.lie_count_weights
    )
    lie_attempts = overrides.lie_attempts or tuple(
        sorted(
            _ranked_attempts(seed, "blueprint:v1:lie-row", range(1, 7))[
                :lie_count
            ]
        )
    )
    lie_tile_counts = overrides.lie_tile_counts or tuple(
        2
        if preset.max_false_tiles >= 2
        and _probability(seed, f"blueprint:v2:two-tile:{attempt}")
        < preset.two_tile_probability
        else 1
        for attempt in lie_attempts
    )
    if len(lie_tile_counts) != len(lie_attempts) or any(
        count not in range(1, preset.max_false_tiles + 1)
        for count in lie_tile_counts
    ):
        raise ValueError("Lie tile counts must align with scheduled lie rows.")

    false_victory_enabled = (
        overrides.false_victory_enabled
        if overrides.false_victory_enabled is not None
        else _probability(seed, "blueprint:v3:false-victory")
        < preset.false_victory_probability
    )

    blackout_attempt: int | None = None
    if overrides.blackout_enabled and preset.blackout_probability > 0:
        blackout_roll = (
            overrides.blackout_roll
            if overrides.blackout_roll is not None
            else _probability(seed, "blueprint:v1:blackout-inclusion")
        )
        if blackout_roll < preset.blackout_probability:
            blackout_attempt = overrides.blackout_attempt
            if blackout_attempt is None:
                blackout_attempt = _ranked_attempts(
                    seed, "blueprint:v1:blackout-row", range(3, 6)
                )[0]

    blackout_blocked = (
        ()
        if blackout_attempt is None
        else (
            (blackout_attempt, blackout_attempt + 1)
            if preset.blackout_reserves_next_attempt
            else (blackout_attempt,)
        )
    )

    timer_events: list[TimerPlan] = []
    if overrides.timer_enabled:
        timer_roll = (
            overrides.timer_roll
            if overrides.timer_roll is not None
            else _probability(seed, "blueprint:v1:timer-inclusion")
        )
        if overrides.timer_attempts is not None:
            timer_count = len(overrides.timer_attempts)
        elif overrides.timer_roll is not None:
            timer_probability = sum(
                weight
                for count, weight in preset.timer_count_weights
                if count > 0
            )
            timer_count = 1 if timer_roll < timer_probability else 0
        else:
            timer_count = _weighted_choice_for_roll(
                timer_roll, preset.timer_count_weights
            )
        forced_attempts = overrides.timer_attempts
        if forced_attempts is None and overrides.timer_attempt is not None:
            forced_attempts = (overrides.timer_attempt,)
        forced_durations = overrides.timer_durations
        if forced_durations is None and overrides.timer_duration is not None:
            forced_durations = (overrides.timer_duration,)
        ranked = _ranked_attempts(seed, "blueprint:v2:timer-row", range(2, 7))
        used: set[int] = set()
        for ordinal in range(timer_count):
            duration = (
                forced_durations[ordinal]
                if forced_durations and ordinal < len(forced_durations)
                else _weighted_choice(
                    seed,
                    f"blueprint:v2:timer-duration:{ordinal + 1}",
                    preset.timer_duration_weights,
                )
            )
            preferred = (
                forced_attempts[ordinal]
                if forced_attempts and ordinal < len(forced_attempts)
                else None
            )

            def eligible(attempt: int) -> bool:
                if attempt in used:
                    return False
                if preset.combination_policy == "none":
                    return attempt not in blackout_blocked
                if (
                    preset.combination_policy == "limited"
                    and duration == 10
                    and blackout_attempt is not None
                ):
                    return attempt != blackout_attempt + 1
                if preset.combination_policy == "broad":
                    prospective = used | {attempt}
                    return not any(
                        {start, start + 1, start + 2} <= prospective
                        for start in range(2, 5)
                    )
                return True

            attempt = preferred if preferred is not None and eligible(preferred) else None
            if attempt is None:
                attempt = next((item for item in ranked if eligible(item)), None)
            if attempt is None:
                continue
            used.add(attempt)
            timer_events.append(TimerPlan(attempt, duration))
        timer_events.sort(key=lambda event: event.attempt)

    # Doubt I permits only one punishment. A scheduled Timer owns that slot;
    # otherwise Reverse Entry remains the possible reactive punishment.
    reverse_enabled = overrides.reverse_enabled and not (
        preset_key == "doubt-1@1" and timer_events
    )

    return GameBlueprint(
        schema_version=3,
        preset_key=preset_key,
        seed=seed,
        lie_attempts=lie_attempts,
        lie_tile_counts=lie_tile_counts,
        false_victory_enabled=false_victory_enabled,
        timer_events=tuple(timer_events),
        reverse_enabled=reverse_enabled,
        reverse_max_events=preset.max_reverse_events,
        reverse_seed=hmac.new(
            seed.encode("utf-8"),
            b"blueprint:v1:reverse-seed",
            hashlib.sha256,
        ).hexdigest(),
        reverse_fallback_probability=preset.reverse_fallback_probability,
        blackout_attempt=blackout_attempt,
        blackout_blocked_attempts=blackout_blocked,
    )
