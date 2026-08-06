from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from functools import lru_cache
import hashlib
import hmac
import json
from types import MappingProxyType
from typing import Literal, Mapping


DEFAULT_PRESET_KEY = "doubt-2@3"
CURRENT_LIE_TILE_CAP = 6


@dataclass(frozen=True)
class LiePolicy:
    count_weights: tuple[tuple[int, float], ...]
    max_false_tiles: int
    two_tile_probability: float
    credible_lie_row_cap: int
    repeat_thread_probability: float


@dataclass(frozen=True)
class PresetDefinition:
    key: str
    name: str
    order: int
    pressure: str
    description: str
    available: bool
    lie_policy: LiePolicy
    false_victory_probability: float
    timer_count_weights: tuple[tuple[int, float], ...]
    timer_duration_weights: tuple[tuple[int, float], ...]
    reverse_fallback_probability: float
    max_reverse_events: int
    blackout_probability: float
    max_blackout_events: int
    blackout_reserves_next_attempt: bool
    intrusion_probability: float
    combination_policy: Literal["none", "limited", "broad"]
    reverse_probability: float = 1.0
    reverse_count_weights: tuple[tuple[int, float], ...] = ((1, 1.0),)
    blind_entry_probability: float = 0.0
    corrupted_history_probability: float = 0.0
    no_revision_probability: float = 0.0
    forced_commitment_probability: float = 0.0
    memory_tax_probability: float = 0.0
    pressure_budget: int = 99
    max_punishment_events: int = 99
    pressure_scene_probability: float = 0.0

    @property
    def lie_count_weights(self) -> tuple[tuple[int, float], ...]:
        return self.lie_policy.count_weights

    @property
    def max_false_tiles(self) -> int:
        return self.lie_policy.max_false_tiles

    @property
    def two_tile_probability(self) -> float:
        return self.lie_policy.two_tile_probability


LEGACY_PRESETS: dict[str, PresetDefinition] = {
        "doubt-1@1": PresetDefinition(
            key="doubt-1@1",
            name="Doubt I",
            order=1,
            pressure="Low",
            description="An approachable introduction to uncertain feedback.",
            available=True,
            lie_policy=LiePolicy(((1, 1.0),), 1, 0.0, 1, 0.0),
            false_victory_probability=0.0,
            timer_count_weights=((0, 0.75), (1, 0.25)),
            timer_duration_weights=((30, 1.0),),
            reverse_fallback_probability=0.05,
            max_reverse_events=1,
            blackout_probability=0.0,
            max_blackout_events=0,
            blackout_reserves_next_attempt=False,
            intrusion_probability=0.0,
            combination_policy="none",
        ),
        "doubt-2@1": PresetDefinition(
            key="doubt-2@1",
            name="Doubt II",
            order=2,
            pressure="Standard",
            description="The complete standard Deception experience.",
            available=True,
            lie_policy=LiePolicy(((1, 0.20), (2, 0.80)), 1, 0.0, 2, 0.0),
            false_victory_probability=0.0,
            timer_count_weights=((0, 0.55), (1, 0.45)),
            timer_duration_weights=((30, 0.70), (10, 0.30)),
            reverse_fallback_probability=0.10,
            max_reverse_events=1,
            blackout_probability=0.20,
            max_blackout_events=1,
            blackout_reserves_next_attempt=True,
            intrusion_probability=0.10,
            combination_policy="none",
        ),
        "doubt-3@1": PresetDefinition(
            key="doubt-3@1",
            name="Doubt III",
            order=3,
            pressure="High",
            description="Aggressive pressure with repeated punishments.",
            available=True,
            lie_policy=LiePolicy(((2, 0.40), (3, 0.60)), 2, 0.25, 3, 0.0),
            false_victory_probability=0.0,
            timer_count_weights=((0, 0.15), (1, 0.55), (2, 0.30)),
            timer_duration_weights=((30, 0.50), (10, 0.50)),
            reverse_fallback_probability=0.20,
            max_reverse_events=2,
            blackout_probability=0.45,
            max_blackout_events=1,
            blackout_reserves_next_attempt=False,
            intrusion_probability=0.30,
            combination_policy="limited",
        ),
        "deception@1": PresetDefinition(
            key="deception@1",
            name="Deception",
            order=4,
            pressure="Extreme",
            description="An expert survival challenge.",
            available=True,
            lie_policy=LiePolicy(
                ((3, 0.15), (4, 0.35), (5, 0.50)), 2, 0.50, 5, 0.0
            ),
            false_victory_probability=0.05,
            timer_count_weights=((1, 0.25), (2, 0.45), (3, 0.30)),
            timer_duration_weights=((30, 0.30), (10, 0.70)),
            reverse_fallback_probability=0.35,
            max_reverse_events=3,
            blackout_probability=0.80,
            max_blackout_events=1,
            blackout_reserves_next_attempt=False,
            intrusion_probability=1.0,
            combination_policy="broad",
        ),
}


def _v2(key: str, **changes: object) -> PresetDefinition:
    legacy = LEGACY_PRESETS[key]
    return replace(legacy, key=key.replace("@1", "@2"), **changes)


V2_PRESETS = {
    "doubt-1@2": _v2(
        "doubt-1@1",
        timer_count_weights=((0, 0.85), (1, 0.15)),
        reverse_probability=0.10,
        reverse_fallback_probability=0.0,
        blind_entry_probability=0.05,
        corrupted_history_probability=0.10,
        pressure_budget=2,
        max_punishment_events=1,
    ),
    "doubt-2@2": _v2(
        "doubt-2@1",
        timer_count_weights=((0, 0.70), (1, 0.30)),
        timer_duration_weights=((30, 0.80), (10, 0.20)),
        reverse_probability=0.15,
        reverse_fallback_probability=0.0,
        blind_entry_probability=0.15,
        corrupted_history_probability=0.20,
        no_revision_probability=0.10,
        forced_commitment_probability=0.05,
        intrusion_probability=0.08,
        pressure_budget=4,
        max_punishment_events=2,
    ),
    "doubt-3@2": _v2(
        "doubt-3@1",
        timer_count_weights=((0, 0.30), (1, 0.525), (2, 0.175)),
        timer_duration_weights=((30, 0.55), (10, 0.45)),
        reverse_probability=0.25,
        reverse_count_weights=((1, 0.75), (2, 0.25)),
        reverse_fallback_probability=0.0,
        blind_entry_probability=0.25,
        corrupted_history_probability=0.20,
        no_revision_probability=0.20,
        forced_commitment_probability=0.15,
        memory_tax_probability=0.30,
        intrusion_probability=0.18,
        pressure_budget=8,
        max_punishment_events=4,
    ),
    "deception@2": _v2(
        "deception@1",
        timer_count_weights=((1, 0.45), (2, 0.40), (3, 0.15)),
        timer_duration_weights=((30, 0.35), (10, 0.65)),
        reverse_probability=0.35,
        reverse_count_weights=((1, 0.60), (2, 0.30), (3, 0.10)),
        reverse_fallback_probability=0.0,
        blind_entry_probability=0.40,
        corrupted_history_probability=0.20,
        no_revision_probability=0.35,
        forced_commitment_probability=0.30,
        memory_tax_probability=0.60,
        intrusion_probability=0.35,
        pressure_budget=13,
        max_punishment_events=7,
    ),
}


def _v3(key: str, **changes: object) -> PresetDefinition:
    current = V2_PRESETS[key]
    return replace(current, key=key.replace("@2", "@3"), **changes)


V3_PRESETS = {
    "doubt-1@3": _v3(
        "doubt-1@2",
        lie_policy=LiePolicy(
            count_weights=((1, 0.85), (2, 0.15)),
            max_false_tiles=1,
            two_tile_probability=0.0,
            credible_lie_row_cap=2,
            repeat_thread_probability=0.04,
        ),
        timer_count_weights=((0, 0.78), (1, 0.22)),
        reverse_probability=0.15,
        blind_entry_probability=0.08,
        corrupted_history_probability=0.12,
        pressure_scene_probability=0.0,
    ),
    "doubt-2@3": _v3(
        "doubt-2@2",
        lie_policy=LiePolicy(
            count_weights=((1, 0.20), (2, 0.75), (3, 0.05)),
            max_false_tiles=1,
            two_tile_probability=0.0,
            credible_lie_row_cap=3,
            repeat_thread_probability=0.10,
        ),
        timer_count_weights=((0, 0.45), (1, 0.55)),
        reverse_probability=0.30,
        blind_entry_probability=0.22,
        corrupted_history_probability=0.25,
        no_revision_probability=0.15,
        forced_commitment_probability=0.10,
        blackout_probability=0.30,
        intrusion_probability=0.12,
        combination_policy="limited",
        pressure_budget=6,
        max_punishment_events=3,
        pressure_scene_probability=0.15,
    ),
    "doubt-3@3": _v3(
        "doubt-3@2",
        lie_policy=LiePolicy(
            count_weights=((2, 0.25), (3, 0.70), (4, 0.05)),
            max_false_tiles=2,
            two_tile_probability=0.35,
            credible_lie_row_cap=4,
            repeat_thread_probability=0.22,
        ),
        timer_count_weights=((0, 0.05), (1, 0.50), (2, 0.45)),
        reverse_probability=0.55,
        reverse_count_weights=((1, 0.55), (2, 0.45)),
        blind_entry_probability=0.40,
        corrupted_history_probability=0.30,
        no_revision_probability=0.35,
        forced_commitment_probability=0.35,
        memory_tax_probability=0.50,
        blackout_probability=0.75,
        intrusion_probability=0.30,
        pressure_budget=12,
        max_punishment_events=7,
        pressure_scene_probability=0.80,
    ),
    "deception@3": _v3(
        "deception@2",
        lie_policy=LiePolicy(
            count_weights=((3, 0.20), (4, 0.75), (5, 0.05)),
            max_false_tiles=2,
            two_tile_probability=0.45,
            credible_lie_row_cap=5,
            repeat_thread_probability=0.35,
        ),
        timer_count_weights=((1, 0.15), (2, 0.45), (3, 0.40)),
        timer_duration_weights=((30, 0.25), (10, 0.75)),
        reverse_probability=0.75,
        reverse_count_weights=((1, 0.35), (2, 0.45), (3, 0.20)),
        blind_entry_probability=0.55,
        corrupted_history_probability=0.30,
        no_revision_probability=0.50,
        forced_commitment_probability=0.55,
        memory_tax_probability=0.80,
        blackout_probability=0.95,
        intrusion_probability=0.50,
        pressure_budget=20,
        max_punishment_events=11,
        pressure_scene_probability=0.95,
    ),
}

PRESETS: Mapping[str, PresetDefinition] = MappingProxyType(
    {**LEGACY_PRESETS, **V2_PRESETS, **V3_PRESETS}
)


def validate_presets() -> None:
    presets = tuple(PRESETS.values())
    if len({preset.key for preset in presets}) != len(presets):
        raise ValueError("Difficulty preset keys must be unique.")
    for mapping_key, preset in PRESETS.items():
        if mapping_key != preset.key:
            raise ValueError(f"Preset registry key does not match definition: {mapping_key}")
        if not preset.key.endswith(("@1", "@2", "@3")):
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
            preset.intrusion_probability,
            preset.reverse_probability,
            preset.blind_entry_probability,
            preset.corrupted_history_probability,
            preset.no_revision_probability,
            preset.forced_commitment_probability,
            preset.memory_tax_probability,
            preset.pressure_scene_probability,
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
    reverse_roll: float | None = None
    intrusion_probability: float | None = None
    timer_enabled: bool = True
    reverse_enabled: bool = True
    blackout_enabled: bool = True
    punishment_plans: tuple[PunishmentPlan, ...] | None = None


@dataclass(frozen=True)
class TimerPlan:
    attempt: int
    duration_seconds: int


PunishmentKind = Literal[
    "timer",
    "reverseEntry",
    "blackout",
    "intrusion",
    "blindEntry",
    "corruptedHistory",
    "noRevision",
    "forcedCommitment",
    "memoryTax",
]


@dataclass(frozen=True)
class PunishmentPlan:
    kind: PunishmentKind
    ordinal: int
    trigger_attempt: int
    effective_attempt: int
    lifecycle: Literal["instant", "nextGuess", "persistent"]
    pressure_cost: int
    config: dict[str, int | str]


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
    intrusion_probability: float
    punishment_plans: tuple[PunishmentPlan, ...] = ()

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

    def punishments_for_trigger(self, attempt: int) -> tuple[PunishmentPlan, ...]:
        return tuple(
            plan for plan in self.punishment_plans
            if plan.trigger_attempt == attempt
        )

    def punishments_for_effective(self, attempt: int) -> tuple[PunishmentPlan, ...]:
        return tuple(
            plan for plan in self.punishment_plans
            if plan.effective_attempt == attempt
            or (
                plan.lifecycle == "persistent"
                and plan.effective_attempt <= attempt <= 6
            )
        )

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
                schema_version=4,
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
                intrusion_probability=0.0,
            )
        if schema_version == 2:
            value["schema_version"] = 3
            value["false_victory_enabled"] = False
            schema_version = 3
        if schema_version == 3:
            value["schema_version"] = 4
            value["intrusion_probability"] = 0.0
        elif schema_version not in {4, 5, 6}:
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
        value["punishment_plans"] = tuple(
            PunishmentPlan(**plan)
            for plan in value.get("punishment_plans", ())
        )
        return cls(**value)


def get_preset(preset_key: str) -> PresetDefinition:
    try:
        return PRESETS[preset_key]
    except KeyError as error:
        raise ValueError(f"Unknown difficulty preset: {preset_key}") from error


def public_presets() -> tuple[PresetDefinition, ...]:
    return tuple(
        sorted(V3_PRESETS.values(), key=lambda preset: preset.order)
    )


@lru_cache(maxsize=128)
def _seed_hmac(seed: str) -> hmac.HMAC:
    return hmac.new(seed.encode("utf-8"), digestmod=hashlib.sha256)


def _number(seed: str, label: str) -> int:
    keyed_hash = _seed_hmac(seed).copy()
    keyed_hash.update(label.encode("utf-8"))
    digest = keyed_hash.digest()
    return int.from_bytes(digest[:8], "big")


@lru_cache(maxsize=256)
def _probability(seed: str, label: str) -> float:
    return _number(seed, label) / 2**64


_PUNISHMENT_COHORT_OFFSETS = {
    "doubt-2@2": {
        "reverseEntry": 0.00, "timer": 0.55, "blackout": 0.45,
        "blindEntry": 0.25, "corruptedHistory": 0.75,
        "noRevision": 0.55, "forcedCommitment": 0.10,
        "memoryTax": 0.00,
    },
    "doubt-3@2": {
        "reverseEntry": 0.00, "timer": 0.70, "blackout": 0.45,
        "blindEntry": 0.45, "corruptedHistory": 0.60,
        "noRevision": 0.20, "forcedCommitment": 0.65,
        "memoryTax": 0.75,
    },
    "deception@2": {
        "reverseEntry": 0.35, "timer": 0.15, "blackout": 0.15,
        "blindEntry": 0.70, "corruptedHistory": 0.60,
        "noRevision": 0.35, "forcedCommitment": 0.00,
        "memoryTax": 0.00,
    },
    "doubt-2@3": {
        "reverseEntry": 0.00, "timer": 0.20, "blackout": 0.45,
        "blindEntry": 0.25, "corruptedHistory": 0.75,
        "noRevision": 0.55, "forcedCommitment": 0.10,
        "memoryTax": 0.00,
    },
    "doubt-3@3": {
        "reverseEntry": 0.00, "timer": 0.70, "blackout": 0.45,
        "blindEntry": 0.45, "corruptedHistory": 0.60,
        "noRevision": 0.20, "forcedCommitment": 0.95,
        "memoryTax": 0.75,
    },
    "deception@3": {
        "reverseEntry": 0.35, "timer": 0.15, "blackout": 0.15,
        "blindEntry": 0.70, "corruptedHistory": 0.60,
        "noRevision": 0.35, "forcedCommitment": 0.00,
        "memoryTax": 0.00,
    },
}


def _punishment_cohort_roll(seed: str, preset_key: str, kind: str) -> float:
    """Return a stable marginal roll while spreading expensive effects.

    A shared cohort value with fixed circular offsets preserves each declared
    probability but avoids the conflict-heavy clusters produced by fully
    independent Bernoulli rolls.
    """
    base = _probability(seed, "blueprint:v5:punishment-cohort")
    offsets = _PUNISHMENT_COHORT_OFFSETS.get(
        preset_key, _PUNISHMENT_COHORT_OFFSETS["doubt-2@2"]
    )
    return (base + offsets[kind]) % 1.0


def _punishment_selected(
    seed: str,
    preset: PresetDefinition,
    kind: str,
    target_probability: float,
) -> bool:
    base = _probability(seed, "blueprint:v5:punishment-cohort")
    if preset.key == "deception@2" and kind == "noRevision":
        return (
            0.27 <= base < 0.40
            or 0.58 <= base < 0.70
            or 0.84 <= base < 0.98
        )
    compensated = target_probability
    if preset.key == "deception@2" and kind == "blindEntry":
        compensated = 0.43
    elif preset.key == "deception@2" and kind == "memoryTax":
        compensated = 0.585
    return _punishment_cohort_roll(seed, preset.key, kind) < compensated


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


INPUT_PUNISHMENTS = {
    "reverseEntry", "blindEntry", "noRevision", "forcedCommitment"
}
_ALLOWED_INPUT_PAIR = frozenset({"reverseEntry", "forcedCommitment"})


def _plans_share_pressure_window(
    first: PunishmentPlan, second: PunishmentPlan
) -> bool:
    if first.lifecycle == "persistent":
        return second.effective_attempt >= first.effective_attempt
    if second.lifecycle == "persistent":
        return first.effective_attempt >= second.effective_attempt
    return first.effective_attempt == second.effective_attempt


def _plan_active_on_attempt(plan: PunishmentPlan, attempt: int) -> bool:
    return (
        attempt >= plan.effective_attempt
        if plan.lifecycle == "persistent"
        else attempt == plan.effective_attempt
    )


def _can_add_punishment(
    preset: PresetDefinition,
    accepted: list[PunishmentPlan],
    candidate: PunishmentPlan,
) -> bool:
    if len(accepted) >= preset.max_punishment_events:
        return False
    if sum(plan.pressure_cost for plan in accepted) + candidate.pressure_cost > preset.pressure_budget:
        return False
    if candidate.kind == "reverseEntry" and any(
        plan.kind == "reverseEntry"
        and plan.effective_attempt == candidate.effective_attempt
        for plan in accepted
    ):
        return False
    same_window = [
        plan for plan in accepted
        if _plans_share_pressure_window(plan, candidate)
    ]
    if preset.combination_policy == "none" and same_window:
        return False
    active_inputs = [
        plan for plan in same_window if plan.kind in INPUT_PUNISHMENTS
    ]
    if candidate.kind in INPUT_PUNISHMENTS and active_inputs:
        proposed_input_kinds = frozenset(
            [candidate.kind, *(plan.kind for plan in active_inputs)]
        )
        if (
            not preset.key.endswith("@3")
            or preset.order < 3
            or proposed_input_kinds != _ALLOWED_INPUT_PAIR
            or len(active_inputs) > 1
        ):
            return False
    timer = next((plan for plan in same_window if plan.kind == "timer"), None)
    if candidate.kind in INPUT_PUNISHMENTS and timer is not None:
        if preset.order <= 2 or preset.combination_policy == "none":
            return False
        if (
            not preset.key.endswith("@3")
            and timer.config.get("durationSeconds") == 10
        ):
            return False
    if candidate.kind == "timer" and candidate.config.get("durationSeconds") == 10:
        if active_inputs and not preset.key.endswith("@3"):
            return False
        if len(active_inputs) >= 2:
            return False
    if candidate.kind in INPUT_PUNISHMENTS and timer is not None:
        if timer.config.get("durationSeconds") == 10 and len(active_inputs) >= 1:
            return False
    if candidate.kind == "timer" and preset.order <= 2 and active_inputs:
        return False
    if candidate.kind == "corruptedHistory" and any(
        plan.kind == "memoryTax" and plan.effective_attempt <= candidate.effective_attempt
        for plan in accepted
    ):
        return False
    if candidate.kind == "memoryTax" and any(
        plan.kind == "blackout"
        and abs(plan.effective_attempt - candidate.effective_attempt) <= 1
        for plan in accepted
    ):
        return False
    if candidate.kind == "blackout" and any(
        plan.kind == "memoryTax"
        and abs(plan.effective_attempt - candidate.effective_attempt) <= 1
        for plan in accepted
    ):
        return False
    blackout_plans = [
        plan for plan in [*accepted, candidate] if plan.kind == "blackout"
    ]
    if preset.order == 2 and blackout_plans:
        blackout_attempt = blackout_plans[0].effective_attempt
        if any(
            plan.kind != "blackout"
            and plan.effective_attempt in {blackout_attempt, blackout_attempt + 1}
            for plan in [*accepted, candidate]
        ):
            return False
    if preset.order == 3 and any(
        plan.kind == "blackout" for plan in same_window
    ):
        timer_plan = candidate if candidate.kind == "timer" else timer
        if (
            timer_plan is not None
            and timer_plan.config.get("durationSeconds") == 10
        ):
            return False
    max_simultaneous = {"none": 1, "limited": 2, "broad": 3}[
        preset.combination_policy
    ]
    for attempt in range(1, 7):
        simultaneous = sum(
            _plan_active_on_attempt(plan, attempt)
            for plan in [*accepted, candidate]
        )
        if simultaneous > max_simultaneous:
            return False
    return True


def _move_plan_to_pressure_window(
    plan: PunishmentPlan,
    effective_attempt: int,
    scene_id: str,
) -> PunishmentPlan:
    config = dict(plan.config)
    config["sceneId"] = scene_id
    if plan.kind == "reverseEntry":
        config["fallbackAttempt"] = effective_attempt
    if plan.kind == "corruptedHistory":
        config["rowAttempt"] = max(1, effective_attempt - 2)
    trigger_attempt = (
        effective_attempt - 1
        if plan.lifecycle in {"nextGuess", "persistent"}
        or plan.kind == "intrusion"
        else effective_attempt
    )
    return replace(
        plan,
        trigger_attempt=trigger_attempt,
        effective_attempt=effective_attempt,
        config=config,
    )


def _coordinate_pressure_scene(
    preset: PresetDefinition,
    seed: str,
    candidates: list[PunishmentPlan],
) -> list[PunishmentPlan]:
    """Align selected effects into one unpredictable but legal pressure scene."""

    if (
        preset.pressure_scene_probability <= 0
        or _probability(seed, "blueprint:v6:pressure-scene")
        >= preset.pressure_scene_probability
    ):
        return candidates
    templates: tuple[tuple[PunishmentKind, ...], ...]
    if preset.order == 2:
        templates = (
            ("timer", "corruptedHistory"),
            ("timer", "intrusion"),
        )
    elif preset.order == 3:
        templates = (
            ("reverseEntry", "forcedCommitment"),
            ("reverseEntry", "timer"),
            ("forcedCommitment", "timer"),
            ("memoryTax", "timer"),
            ("timer", "intrusion"),
            ("blackout", "timer"),
            ("blackout", "intrusion"),
        )
    else:
        templates = (
            ("reverseEntry", "forcedCommitment", "timer"),
            ("blackout", "reverseEntry", "timer"),
            ("blackout", "timer", "intrusion"),
            ("reverseEntry", "forcedCommitment"),
            ("reverseEntry", "timer"),
            ("forcedCommitment", "timer"),
            ("blindEntry", "timer"),
            ("noRevision", "timer"),
            ("memoryTax", "timer"),
            ("timer", "intrusion"),
            ("blackout", "timer"),
        )
    ranked_templates = sorted(
        templates,
        key=lambda template: _number(
            seed, f"blueprint:v6:scene-template:{','.join(template)}"
        ),
    )
    by_kind = {
        kind: next((plan for plan in candidates if plan.kind == kind), None)
        for kind in {kind for template in templates for kind in template}
    }
    selected_template = next(
        (
            template
            for template in ranked_templates
            if all(by_kind[kind] is not None for kind in template)
            and not (
                len(template) == 3
                and by_kind["timer"] is not None
                and by_kind["timer"].config.get("durationSeconds") == 10
            )
            and not (
                preset.order == 3
                and "blackout" in template
                and "timer" in template
                and by_kind["timer"] is not None
                and by_kind["timer"].config.get("durationSeconds") == 10
            )
        ),
        None,
    )
    if selected_template is None:
        return candidates
    eligible_attempts = (
        range(3, 6)
        if "blackout" in selected_template
        else range(3, 5)
        if "memoryTax" in selected_template
        else range(2, 7)
    )
    effective_attempt = _ranked_attempts(
        seed, "blueprint:v6:scene-attempt", eligible_attempts
    )[0]
    scene_id = hashlib.sha256(
        f"{seed}:{','.join(selected_template)}".encode("utf-8")
    ).hexdigest()[:12]
    selected_ids = {id(by_kind[kind]) for kind in selected_template}
    return [
        _move_plan_to_pressure_window(plan, effective_attempt, scene_id)
        if id(plan) in selected_ids
        else plan
        for plan in candidates
    ]


def _new_punishment_candidates(
    preset: PresetDefinition,
    seed: str,
) -> list[PunishmentPlan]:
    candidates: list[PunishmentPlan] = []
    definitions = (
        ("blindEntry", preset.blind_entry_probability, 2, "nextGuess"),
        ("corruptedHistory", preset.corrupted_history_probability, 1, "nextGuess"),
        ("noRevision", preset.no_revision_probability, 2, "nextGuess"),
        ("forcedCommitment", preset.forced_commitment_probability, 3, "nextGuess"),
    )
    for kind, probability, cost, lifecycle in definitions:
        if not _punishment_selected(seed, preset, kind, probability):
            continue
        effective = _ranked_attempts(
            seed, f"blueprint:v5:{kind}:attempt", range(2, 7)
        )[0]
        config: dict[str, int | str] = {}
        if kind == "corruptedHistory":
            config["rowAttempt"] = max(1, effective - 2)
        candidates.append(
            PunishmentPlan(
                kind=kind, ordinal=1, trigger_attempt=effective - 1,
                effective_attempt=effective, lifecycle=lifecycle,
                pressure_cost=cost, config=config,
            )
        )
    if (
        preset.memory_tax_probability > 0
        and _punishment_selected(
            seed, preset, "memoryTax", preset.memory_tax_probability
        )
    ):
        trigger = _ranked_attempts(
            seed, "blueprint:v5:memoryTax:attempt", range(3, 5)
        )[0]
        candidates.append(
            PunishmentPlan(
                kind="memoryTax", ordinal=1, trigger_attempt=trigger,
                effective_attempt=trigger, lifecycle="persistent",
                pressure_cost=3, config={"retainRows": 2},
            )
        )
    return candidates


def build_blueprint(
    preset_key: str,
    seed: str,
    overrides: BlueprintOverrides = BlueprintOverrides(),
) -> GameBlueprint:
    """Build one deterministic, immutable game blueprint."""
    preset = get_preset(preset_key)
    if not preset.available:
        raise ValueError(f"Difficulty preset is not available: {preset_key}")
    if (
        overrides.intrusion_probability is not None
        and not 0 <= overrides.intrusion_probability <= 1
    ):
        raise ValueError("Intrusion probability must be between zero and one.")

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
    if (
        preset_key.endswith("@3")
        and overrides.lie_tile_counts is not None
        and sum(lie_tile_counts) > CURRENT_LIE_TILE_CAP
    ):
        raise ValueError(
            f"Current presets permit at most {CURRENT_LIE_TILE_CAP} false tiles."
        )
    if preset_key.endswith("@3") and sum(lie_tile_counts) > CURRENT_LIE_TILE_CAP:
        available_two_tile_slots = max(
            0, CURRENT_LIE_TILE_CAP - len(lie_attempts)
        )
        retained_two_tile_attempts = set(
            _ranked_attempts(
                seed,
                "blueprint:v3:lie-tile-cap",
                tuple(
                    attempt
                    for attempt, count in zip(lie_attempts, lie_tile_counts)
                    if count == 2
                ),
            )[:available_two_tile_slots]
        )
        lie_tile_counts = tuple(
            2 if attempt in retained_two_tile_attempts else 1
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
            else (
                _punishment_cohort_roll(seed, preset_key, "blackout")
                if preset_key.endswith(("@2", "@3"))
                else _probability(seed, "blueprint:v1:blackout-inclusion")
            )
        )
        blackout_probability = (
            0.79 if preset_key == "deception@2"
            else preset.blackout_probability
        )
        if blackout_roll < blackout_probability:
            blackout_attempt = overrides.blackout_attempt
            if blackout_attempt is None:
                blackout_attempt = (
                    _weighted_choice(
                        seed,
                        "blueprint:v6:blackout-row",
                        (
                            ((3, 0.15), (4, 0.45), (5, 0.40))
                            if preset_key == "doubt-3@3"
                            else ((3, 0.10), (4, 0.45), (5, 0.45))
                        ),
                    )
                    if preset_key in {"doubt-3@3", "deception@3"}
                    else _ranked_attempts(
                        seed, "blueprint:v1:blackout-row", range(3, 6)
                    )[0]
                )

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
            else (
                _punishment_cohort_roll(seed, preset_key, "timer")
                if preset_key.endswith(("@2", "@3"))
                else _probability(seed, "blueprint:v1:timer-inclusion")
            )
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
                else (
                    30
                    if preset_key == "deception@2"
                    and 0.30 <= _probability(
                        seed, "blueprint:v5:punishment-cohort"
                    ) < 0.60
                    else 10
                )
                if preset_key == "deception@2"
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

    if preset_key.endswith("@1"):
        reverse_enabled = overrides.reverse_enabled and not (
            preset_key == "doubt-1@1" and timer_events
        )
        return GameBlueprint(
            schema_version=4,
            preset_key=preset_key,
            seed=seed,
            lie_attempts=lie_attempts,
            lie_tile_counts=lie_tile_counts,
            false_victory_enabled=false_victory_enabled,
            timer_events=tuple(timer_events),
            reverse_enabled=reverse_enabled,
            reverse_max_events=preset.max_reverse_events,
            reverse_seed=hmac.new(
                seed.encode("utf-8"), b"blueprint:v1:reverse-seed",
                hashlib.sha256,
            ).hexdigest(),
            reverse_fallback_probability=preset.reverse_fallback_probability,
            blackout_attempt=blackout_attempt,
            blackout_blocked_attempts=blackout_blocked,
            intrusion_probability=(
                overrides.intrusion_probability
                if overrides.intrusion_probability is not None
                else preset.intrusion_probability
            ),
        )

    candidates: list[PunishmentPlan] = []
    for ordinal, event in enumerate(timer_events, start=1):
        candidates.append(
            PunishmentPlan(
                kind="timer", ordinal=ordinal,
                trigger_attempt=event.attempt - 1,
                effective_attempt=event.attempt,
                lifecycle="nextGuess",
                pressure_cost=1 if event.duration_seconds == 30 else 3,
                config={"durationSeconds": event.duration_seconds},
            )
        )
    if blackout_attempt is not None:
        candidates.append(
            PunishmentPlan(
                kind="blackout", ordinal=1,
                trigger_attempt=blackout_attempt,
                effective_attempt=blackout_attempt,
                lifecycle="instant", pressure_cost=3, config={},
            )
        )

    reverse_selected = (
        overrides.reverse_enabled
        and (
            overrides.reverse_roll
            if overrides.reverse_roll is not None
            else _punishment_cohort_roll(seed, preset_key, "reverseEntry")
        )
        < preset.reverse_probability
    )
    if reverse_selected:
        reverse_count = _weighted_choice(
            seed, "blueprint:v5:reverseEntry:count",
            preset.reverse_count_weights,
        )
        for ordinal, effective in enumerate(
            sorted(
                _ranked_attempts(
                    seed,
                    "blueprint:v5:reverseEntry:attempt",
                    range(2, 7),
                )[:reverse_count]
            ),
            start=1,
        ):
            candidates.append(
                PunishmentPlan(
                    kind="reverseEntry", ordinal=ordinal,
                    trigger_attempt=effective - 1,
                    effective_attempt=effective,
                    lifecycle="nextGuess", pressure_cost=2,
                    config={"fallbackAttempt": effective},
                )
            )

    candidates.extend(_new_punishment_candidates(preset, seed))
    intrusion_probability = (
        overrides.intrusion_probability
        if overrides.intrusion_probability is not None
        else preset.intrusion_probability
    )
    intrusion_selection_probability = (
        intrusion_probability
        if overrides.intrusion_probability is not None
        else {
            "doubt-2@2": 0.14,
            "doubt-3@2": 0.28,
            "deception@2": 1.00,
            "doubt-2@3": preset.intrusion_probability,
            "doubt-3@3": preset.intrusion_probability,
            "deception@3": preset.intrusion_probability,
        }.get(preset_key, intrusion_probability)
    )
    intrusion_offsets = {
        "doubt-2@2": (0.00, 0.80, 0.60, 0.40),
        "doubt-3@2": (0.00, 0.80, 0.60, 0.40),
        "deception@2": (0.00, 0.75, 0.50, 0.25),
        "doubt-2@3": (0.00, 0.80, 0.60, 0.40),
        "doubt-3@3": (0.00, 0.80, 0.60, 0.40),
        "deception@3": (0.00, 0.75, 0.50, 0.25),
    }
    intrusion_base = _probability(seed, "blueprint:v5:punishment-cohort")
    ordinal = 0
    for index, attempt in enumerate(range(2, 6)):
        offsets = intrusion_offsets.get(preset_key)
        roll = (
            (intrusion_base + offsets[index]) % 1.0
            if offsets is not None
            else _probability(seed, f"blueprint:v5:intrusion:{attempt}")
        )
        if roll >= intrusion_selection_probability:
            continue
        ordinal += 1
        candidates.append(
            PunishmentPlan(
                kind="intrusion", ordinal=ordinal,
                trigger_attempt=attempt, effective_attempt=attempt,
                lifecycle="instant", pressure_cost=1,
                config={
                    "placementIndex": _number(
                        seed, f"blueprint:v5:intrusion-placement:{attempt}"
                    ) % 4
                },
            )
        )

    if preset_key in {"doubt-1@2", "doubt-1@3"}:
        roll = _probability(seed, "blueprint:v5:doubt-one-category")
        reverse_cutoff = preset.reverse_probability
        timer_cutoff = reverse_cutoff + sum(
            weight for count, weight in preset.timer_count_weights if count > 0
        )
        blind_cutoff = timer_cutoff + preset.blind_entry_probability
        corrupted_cutoff = blind_cutoff + preset.corrupted_history_probability
        if roll < reverse_cutoff:
            kind = "reverseEntry"
        elif roll < timer_cutoff:
            kind = "timer"
        elif roll < blind_cutoff:
            kind = "blindEntry"
        elif roll < corrupted_cutoff:
            kind = "corruptedHistory"
        else:
            kind = ""
        candidates = [plan for plan in candidates if plan.kind == kind][:1]
        if kind and not candidates:
            effective = _ranked_attempts(
                seed, f"blueprint:v5:{kind}:categorical", range(2, 7)
            )[0]
            candidates = [
                PunishmentPlan(
                    kind=kind, ordinal=1,
                    trigger_attempt=effective - 1,
                    effective_attempt=effective,
                    lifecycle="nextGuess",
                    pressure_cost={
                        "timer": 1, "reverseEntry": 2,
                        "blindEntry": 2, "corruptedHistory": 1,
                    }[kind],
                    config=(
                        {"durationSeconds": 30} if kind == "timer"
                        else ({"fallbackAttempt": effective}
                              if kind == "reverseEntry" else {})
                    ),
                )
            ]

    if overrides.punishment_plans is not None:
        candidates = list(overrides.punishment_plans)
    elif preset_key.endswith("@3"):
        candidates = _coordinate_pressure_scene(preset, seed, candidates)

    memory = next((plan for plan in candidates if plan.kind == "memoryTax"), None)
    blackout = next((plan for plan in candidates if plan.kind == "blackout"), None)
    if (
        memory is not None
        and blackout is not None
        and abs(memory.effective_attempt - blackout.effective_attempt) <= 1
    ):
        # The only universally compatible late-game pairing is Memory Tax on
        # row three followed by Blackout on row five.
        candidates = [
            replace(plan, trigger_attempt=3, effective_attempt=3)
            if plan is memory
            else replace(plan, trigger_attempt=5, effective_attempt=5)
            if plan is blackout
            else plan
            for plan in candidates
        ]

    # Preserve the player-facing encounter targets for the established anchor
    # punishments before filling the remaining pressure budget. The ordering
    # within each family stays deterministic and seed-dependent.
    accepted: list[PunishmentPlan] = []
    forced_kinds: set[str] = set()
    if overrides.timer_attempt is not None or overrides.timer_attempts is not None:
        forced_kinds.add("timer")
    if overrides.blackout_attempt is not None:
        forced_kinds.add("blackout")
    if overrides.reverse_roll is not None:
        forced_kinds.add("reverseEntry")
    for candidate in sorted(
        candidates,
        key=lambda plan: (
            0 if plan.kind in forced_kinds else 1,
            0 if "sceneId" in plan.config else 1,
            (
                {
                    "timer": 0,
                    "reverseEntry": 1,
                    "memoryTax": 2,
                    "blackout": 3,
                    "forcedCommitment": 4,
                    "blindEntry": 4,
                    "noRevision": 4,
                    "corruptedHistory": 4,
                    "intrusion": 5,
                }
                if preset_key.endswith("@3")
                else {
                    "memoryTax": 0,
                    "blackout": 1,
                    "timer": 2,
                    "reverseEntry": 3,
                    "forcedCommitment": 4,
                    "blindEntry": 4,
                    "noRevision": 4,
                    "corruptedHistory": 4,
                    "intrusion": 5,
                }
            ).get(plan.kind, 9),
            _number(
                seed,
                f"blueprint:v5:priority:{plan.kind}:{plan.ordinal}:{plan.effective_attempt}",
            ),
        ),
    ):
        selected = (
            candidate
            if _can_add_punishment(preset, accepted, candidate)
            else None
        )
        if (
            selected is None
            and candidate.kind in INPUT_PUNISHMENTS | {"corruptedHistory"}
        ):
            for effective in _ranked_attempts(
                seed,
                f"blueprint:v5:reroute:{candidate.kind}:{candidate.ordinal}",
                range(2, 7),
            ):
                if effective == candidate.effective_attempt:
                    continue
                config = dict(candidate.config)
                if candidate.kind == "corruptedHistory":
                    config["rowAttempt"] = max(1, effective - 2)
                if candidate.kind == "reverseEntry":
                    config["fallbackAttempt"] = effective
                alternative = replace(
                    candidate,
                    trigger_attempt=effective - 1,
                    effective_attempt=effective,
                    config=config,
                )
                if _can_add_punishment(preset, accepted, alternative):
                    selected = alternative
                    break
        if selected is not None:
            accepted.append(selected)
    accepted.sort(key=lambda plan: (plan.trigger_attempt, plan.kind, plan.ordinal))

    timer_events = [
        TimerPlan(
            plan.effective_attempt,
            int(plan.config["durationSeconds"]),
        )
        for plan in accepted if plan.kind == "timer"
    ]
    blackout_plan = next(
        (plan for plan in accepted if plan.kind == "blackout"), None
    )
    blackout_attempt = (
        blackout_plan.trigger_attempt if blackout_plan is not None else None
    )
    blackout_blocked = (
        () if blackout_attempt is None else
        ((blackout_attempt, blackout_attempt + 1)
         if preset.blackout_reserves_next_attempt else (blackout_attempt,))
    )
    reverse_plans = [
        plan for plan in accepted if plan.kind == "reverseEntry"
    ]
    reverse_enabled = bool(reverse_plans)

    return GameBlueprint(
        schema_version=6 if preset_key.endswith("@3") else 5,
        preset_key=preset_key,
        seed=seed,
        lie_attempts=lie_attempts,
        lie_tile_counts=lie_tile_counts,
        false_victory_enabled=false_victory_enabled,
        timer_events=tuple(timer_events),
        reverse_enabled=reverse_enabled,
        reverse_max_events=len(reverse_plans),
        reverse_seed=hmac.new(
            seed.encode("utf-8"),
            b"blueprint:v1:reverse-seed",
            hashlib.sha256,
        ).hexdigest(),
        reverse_fallback_probability=preset.reverse_fallback_probability,
        blackout_attempt=blackout_attempt,
        blackout_blocked_attempts=blackout_blocked,
        intrusion_probability=intrusion_probability,
        punishment_plans=tuple(accepted),
    )


IntrusionPlacement = Literal[
    "upperLeft", "upperRight", "lowerLeft", "lowerRight"
]


def intrusion_for_attempt(
    blueprint: GameBlueprint,
    attempt: int,
) -> IntrusionPlacement | None:
    """Return this accepted row's deterministic Intrusion, if any."""
    if attempt not in range(2, 6):
        return None
    scheduled = next(
        (
            plan for plan in blueprint.punishment_plans
            if plan.kind == "intrusion" and plan.trigger_attempt == attempt
        ),
        None,
    )
    if scheduled is not None:
        placements: tuple[IntrusionPlacement, ...] = (
            "upperLeft", "upperRight", "lowerLeft", "lowerRight"
        )
        return placements[int(scheduled.config.get("placementIndex", 0))]
    if blueprint.schema_version >= 5:
        return None
    if (
        _probability(blueprint.seed, f"blueprint:v4:intrusion:{attempt}")
        >= blueprint.intrusion_probability
    ):
        return None
    placements: tuple[IntrusionPlacement, ...] = (
        "upperLeft",
        "upperRight",
        "lowerLeft",
        "lowerRight",
    )
    index = _number(
        blueprint.seed, f"blueprint:v4:intrusion-placement:{attempt}"
    ) % len(placements)
    return placements[index]
