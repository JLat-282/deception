# Design: Difficulty Presets and Daily Descent

## Preset generation 3 (current)

New games use the `@3` preset family and blueprint schema 6. Stored `@1` and
`@2` games retain their persisted blueprint and lie-strategy version. A Daily
Descent puzzle set is pinned for the entire reset window; a deployment cannot
upgrade a run between stages.

| Preset | Scheduled lie rows | Two-tile chance | Repeat-thread chance |
|---|---:|---:|---:|
| `doubt-1@3` | 1: 85%, 2: 15% | 0% | 4% |
| `doubt-2@3` | 1: 20%, 2: 75%, 3: 5% | 0% | 10% |
| `doubt-3@3` | 2: 25%, 3: 70%, 4: 5% | 35% per row | 22% |
| `deception@3` | 3: 20%, 4: 75%, 5: 5% | 45% per row | 35% |

Exact lie rows are uniformly selected without replacement from attempts one
through six. There are no phase quotas, set row patterns, or adaptive
rubber-banding. Winning guesses and attempt six stay truthful. A selected row
can remain truthful when no candidate passes the contextual quality gate.
Across every current game, no more than six displayed tiles may differ from
their truthful feedback. A row may suppress at most one genuine green or yellow
to gray, and the whole game may do so at most twice. When both a suppression and
an information-preserving lie are plausible, the engine selects suppression 25%
of the time; otherwise it uses the available valid style. Remaining lies invent
plausible signals or confuse position.

Generation 3 replaces exact-decoy-only plausibility with a player-belief model.
A credible world is an alternate answer plus a difficulty-bounded explanation
of which displayed tiles could already have lied. Early rows therefore retain
broad deceptive freedom even after an unusually strong first guess. Later rows
use a higher quality threshold, allowing unsupported rare-letter probes to stay
truthful. Repeat threads may revisit a previously lied-about letter at every
level without making that tactic the default.

The punishment director preserves random event timing while introducing
compatibility-tested pressure scenes. Doubt III and Deception may combine
Reverse Entry with Forced Commitment. A ten-second Timer never joins that
two-input stack. Distinct Reverse Entry events may occupy consecutive guesses;
an event never carries into another guess after its timed attempt expires. The
UI stacks concise active-punishment names in one status region. The
result view audits lies only; it does not recap punishments the player already
experienced.

| Punishment selection | Doubt I | Doubt II | Doubt III | Deception |
|---|---:|---:|---:|---:|
| Timer, at least once | 22% | 55% | 95% | 100% |
| Reverse Entry | 15% | 30% | 55% | 75% |
| Blind Entry | 8% | 22% | 40% | 55% |
| Corrupted History | 12% | 25% | 30% | 30% |
| No Revision | 0% | 15% | 35% | 50% |
| Forced Commitment | 0% | 10% | 35% | 55% |
| Memory Tax | 0% | 0% | 50% | 80% |
| Blackout | 0% | 30% | 75% | 95% |
| Intrusion, per eligible row | 0% | 12% | 30% | 50% |
| Coordinated pressure scene | 0% | 15% | 80% | 95% |

Doubt III schedules zero, one, or two Timers at 5%, 50%, and 45%. Deception
schedules one, two, or three at 15%, 45%, and 40%. Doubt III selects one or two
Reverse Entry events at 55% and 45% after the game qualifies for Reverse Entry;
Deception selects one, two, or three at 35%, 45%, and 20%. Pressure budgets and
event caps are 2/1, 6/3, 12/7, and 20/11 across the four levels. Compatibility
validation can suppress a selected event, so enforced simulations also gate
post-validation encounter rates, same-attempt Reverse-plus-Timer pressure, and
quiet-blueprint frequency. Blackout remains limited to guesses three through
five and is weighted toward guesses four and five on the top two levels.

Performance gates are enforced by repository commands: common lie decisions
must remain at or below 25ms p99, maximum-history and two-tile decisions at or
below 35ms p99, with a 50ms p99.9 ceiling. Blueprint generation must remain at
or below 5ms p99 through Doubt III. Maximum-pressure Deception blueprints have
a 10ms p99 and 20ms p99.9 ceiling. Raw maxima are reported for diagnosis but do
not fail the gate because OS scheduling pauses are not engine work. The 100,000-seed
balance simulation checks declared marginals, legal overlap, pressure bands,
and generation latency.

## Preset generation 2 (stored-game compatibility)

Generation 2 games use the `@2` preset family and blueprint schema 5. Stored
`@1` games retain their original behavior. Schema-5 blueprints contain normalized
punishment plans with trigger attempts, effective attempts, lifecycle, pressure
cost, and private configuration, so compatibility is checked against the guess
actually affected.

The additional punishments are Blind Entry, Corrupted History, Forced
Commitment, No Revision, and Memory Tax. Only one input modifier can affect a
guess, ten-second timers cannot combine with input modifiers, and Memory Tax
keeps the two newest rows until terminal history restoration.

Reverse Entry targets an encountered event in 10%, 15%, 25%, and 35% of Doubt
I, Doubt II, Doubt III, and Deception games. Doubt I uses one categorical
punishment slot. Higher levels use pressure budgets of 4, 8, and 13 with event
caps of 2, 4, and 7. Intrusion returns from its temporary Deception testing
override to a 35% per-eligible-row selection rate.

Generated through product workshop on 2026-08-03  
Branch: `main`  
Status: GENERATION 3 IMPLEMENTED; PLAYTEST CALIBRATION PENDING
Mode: Builder

## Problem Statement

Deception needs difficulty levels that feel meaningfully different without telling
players which lies or punishments are coming. The easiest level should remain a
solvable introduction to distrusting feedback. The highest level should be an
expert survival challenge: effectively unwinnable for an average player, but still
capable of producing roughly a 10-20% win rate for expert players after tuning.

Difficulty must not become arbitrary coloring or unavoidable failure. Increasing
difficulty should come from more frequent believable lies, repeated punishments,
and carefully controlled combinations.

## What Makes This Cool

The player never selects a transparent checklist of handicaps. They select how much
pressure they are willing to face, while the game secretly constructs a reproducible
challenge inside that pressure range. Daily mode becomes a four-stage descent where
the meaningful result is not only whether the player won, but how deep they survived.

## Locked Player-Facing Structure

The four presets are:

1. **Doubt I**
2. **Doubt II**
3. **Doubt III**
4. **Deception**

All four difficulties are freely selectable in Practice and the future Infinite
mode. Deception is not permanently locked behind progression.

Roman numerals may communicate ordering, but the final preset is named
**Deception**, not **Doubt IV**.

## Difficulty Contract

The following rules are shared by every preset:

- Answers remain five letters and games remain six accepted attempts.
- Vocabulary difficulty and guess count are not difficulty axes.
- Exact lie counts, punishment counts, timing, and order remain hidden.
- Winning guesses and terminal feedback remain truthful.
- A row may display at most two coordinated false feedback tiles.
- A lie changes feedback only; tile movement and letter transformation remain
  punishments.
- Blackout may occur at most once per stage.
- Every completed stage reveals its answer and lie report.
- Accessibility equivalents must preserve the challenge without exposing the
  hidden schedule.

Difficulty increases along four distinct configurable axes:

1. Scheduled lie opportunities.
2. Maximum false tiles per eligible row.
3. Punishment frequency and repetition.
4. Permission to combine punishments around the same attempt.

These are distinct configurable axes, not statistically independent variables.
The scheduler is allowed to couple them to enforce a level's pressure and
compatibility rules.

## Glossary

- **Eligible nonterminal row:** An accepted attempt from one through five. A
  correct answer normally ends the stage, except for Deception's rare, bounded
  False Victory rule on guesses two through four.
- **Scheduled lie row:** An attempt index on which the lie planner may alter
  feedback. It may remain truthful if no safe mutation exists or the game ends
  before that attempt.
- **Experienced event:** A scheduled or reactive event that actually activates
  during play. Early wins may prevent blueprint events from being experienced.
- **Quiet blueprint:** A generated blueprint below its preset's required minimum
  scheduled pressure. This is prohibited in Doubt III and Deception. An early win
  or truthful lie fallback does not retroactively make a valid blueprint quiet.
- **Stage consumption:** The atomic acceptance of the first valid guess for that
  stage. Invalid, incomplete, or rejected submissions do not consume it.
- **Terminal feedback:** Feedback for the accepted guess that ends the stage.
  Guesses five and six always recognize a correct answer, and attempt six always
  displays truthful feedback.
- **Immutable blueprint:** The persisted schedulable challenge created before play.
  It includes seeds for reactive decisions but not their future realized outcomes.
- **Runtime event:** A deterministic event derived from the immutable blueprint and
  actual guess history.
- **Pressure target:** A versioned numeric budget and event-count range defined by a
  preset. Its first values remain part of the tuning gate.

## Initial Preset Matrix

This matrix locks the shape of each level. The first numeric playtest hypotheses
were approved on 2026-08-03 and are versioned below so later tuning does not
silently change active games.

| Axis | Doubt I | Doubt II | Doubt III | Deception |
|---|---|---|---|---|
| Intended experience | Approachable distrust | Complete standard experience | Aggressive combined pressure | Expert survival challenge |
| Scheduled lie rows | 1-2 | 1-3 | 2-4 | 3-5 eligible nonterminal rows |
| False tiles per lying row | Maximum 1 | Maximum 1 | Maximum 2 | Maximum 2 |
| Guess Timer | At most once | At most once | May repeat | May repeat |
| Reverse Entry | At most once | At most once | May repeat | May repeat |
| Blackout | Disabled | At most once | At most once | At most once |
| Intrusion | Disabled | May repeat | May repeat | May repeat |
| Same-attempt combinations | None | None | Limited allowlist | Broad allowlist |
| Quiet-blueprint risk | Allowed only inside the approachable envelope | Low | Not allowed | Not allowed |

### Version 1 playtest tuning matrix

| Setting | `doubt-1@1` | `doubt-2@1` | `doubt-3@1` | `deception@1` |
|---|---:|---:|---:|---:|
| Scheduled lie rows | 1 | 1: 20%, 2: 80% | 2: 40%, 3: 60% | 3: 15%, 4: 35%, 5: 50% |
| Two-tile lie allowance | Never | Never | 25% per lie row | 50% per lie row |
| False Victory permission | Never | Never | Never | 5% of games; once on guesses 2-4 |
| Timer events | 25% chance of 1 | 45% chance of 1 | 0: 15%, 1: 55%, 2: 30% | 1: 25%, 2: 45%, 3: 30% |
| Timer duration | 30s: 100% | 30s: 70%, 10s: 30% | 30s: 50%, 10s: 50% | 30s: 30%, 10s: 70% |
| Reverse fallback chance | 5% | 10% | 20% | 35% |
| Maximum Reverse events | 1 | 1 | 2 | 3 |
| Blackout chance | Disabled | 20% | 45% | 80% |
| Blackout maximum | 0 | 1 | 1 | 1 |
| Intrusion chance per accepted row (2-5) | 0% | 10% | 30% | 60% |

The existing four-or-five-displayed-gray trigger remains eligible at every
preset independently of the fallback probability.

Version 1 compatibility rules:

- `doubt-1@1`: at most one punishment in the game. Timer takes priority over
  Reverse Entry on collision.
- `doubt-2@1`: no same-attempt combinations. Blackout reserves its own attempt
  and the following attempt.
- `doubt-3@1`: Timer, Reverse Entry, and Blackout may combine. A 30-second
  Timer may begin after Blackout finishes opening; a 10-second Timer may not
  share that transition and is deterministically moved to another eligible
  turn. Timer and Reverse Entry may occur on consecutive attempts.
- `deception@1`: Timer, Reverse Entry, and Blackout may combine, including all
  three from the same completed guess. A Timer begins after the curtain reopens.
  Timer may repeat on adjacent attempts but never on three consecutive attempts.
  Reverse Entry may repeat on consecutive attempts.
- Intrusion is rolled independently after each accepted, non-winning guess on
  attempts two through five. It has no per-game cap and may repeat on
  consecutive attempts. It takes over the screen until its moving Dismiss
  control is activated, but an active Timer continues. When Intrusion and
  Blackout share a row, the curtain completes before Intrusion appears.

These numbers are hypotheses for playtesting rather than permanent balance
promises. Any change creates a new preset version.

Interpretation notes:

- A scheduled lie row is an opportunity, not a guaranteed false tile. The lie
  planner may remain truthful if it cannot find a plausible mutation.
- Deception may affect every eligible nonterminal row, but does not have to do so
  in every game.
- The two-tile cap prevents higher difficulties from becoming random-looking
  full-row recolors.
- Timer and Reverse Entry can appear multiple times in Doubt III and Deception.
- Repeated Blackout is prohibited even at the highest difficulty.
- Repeated Intrusion is allowed; its uncertainty comes from a fresh,
  deterministic per-row roll rather than a preannounced event count.
- False Victory is independently enabled in 5% of Deception blueprints. It can
  reject one correct answer only on a scheduled lie row from attempts two through
  four, requires a plausible mutation, and permanently protects later submissions
  of that answer.

### Doubt II version 1 baseline

Doubt II is the migration target for the current complete game. Its initial
blueprint must preserve these existing rules until deliberately retuned:

- One scheduled lie row 20% of the time and two rows 80% of the time.
- At most one altered tile on each scheduled lie row.
- At most one Guess Timer, scheduled in 45% of games.
- A scheduled timer is 30 seconds 70% of the time and 10 seconds 30% of the
  time.
- At most one Reverse Entry, triggered by four or five displayed absent tiles or
  the existing 10% fallback roll.
- At most one Blackout, scheduled in 20% of games on attempt three, four, or five.
- Timer and Reverse Entry do not affect the same guess.
- Blackout excludes Timer and Reverse Entry on its attempt and the immediately
  following attempt.

This baseline is identified as `doubt-2@1`; later tuning creates a new version
instead of silently changing active games.

The values above are immutable for `doubt-2@1`. Milestone 0 does not retune them,
and the Doubt II migration acceptance test compares against this exact baseline.
The first later tuning pass was introduced as `doubt-2@2`; generation 3 now
owns the defaults for newly created games.

## Recommended Architecture: Hidden Pressure Scheduler

Difficulty must not be implemented as a collection of independent probability
checks. Independent rolls can produce a quiet Deception game, an accidentally
overloaded Doubt game, or complex collision repair.

Before a game begins, a hidden pressure scheduler creates and persists an immutable
schedulable challenge blueprint. The blueprint contains:

- Preset identifier and rules version.
- Shared challenge seed when applicable.
- Lie-row schedule and per-row false-tile allowance.
- Preassigned punishment types and eligible attempts.
- Timer duration choices.
- Per-type repetition caps.
- Same-attempt and adjacent-attempt compatibility decisions.
- Seeds and derivation versions for reactive runtime events.

The scheduler follows this order:

1. Load the selected preset.
2. Select a pressure target inside the preset's permitted range.
3. Schedule lie opportunities.
4. Allocate punishment events without exceeding type caps.
5. Apply the compatibility matrix and cooldown rules.
6. Verify hard fairness constraints.
7. Persist the final blueprint before accepting the first guess.

The scheduler guarantees a recognizable pressure envelope while keeping the exact
challenge unknowable to the player.

Blueprints and preset versions are server-only until the stage ends. Bootstrap,
stage-start, and active-guess responses never expose hidden attempts, seeds, unused
events, truthful feedback behind a lie, or decoy candidates. The terminal stage
report may reveal the answer, activated and avoided lie opportunities, and
punishments that activated or were never reached.

### Reactive punishments

Not every punishment can be identical across players because some triggers depend
on player choices. Reverse Entry, for example, may react to displayed feedback from
the player's previous guess.

For Daily Descent:

- The answer, preset, challenge seed, lie opportunities, and all schedulable
  punishment decisions are shared.
- Reactive rules are identical for every player.
- Any reactive random branch is derived deterministically from the daily seed,
  stage, attempt, event type, and relevant guess history.
- Two players who submit identical guess histories receive identical outcomes.
- Different guesses may legitimately produce different reactive punishments.

This is deterministic fairness, not forced identical play.

## Punishment Compatibility

The compatibility matrix is data owned by each difficulty preset. It must answer:

- Can Timer and Reverse Entry affect the same guess?
- Can a Timer begin immediately after Blackout?
- Can Reverse Entry begin immediately after Blackout?
- Does Blackout reserve its following attempt?
- How many attempts of cooldown does each punishment require?
- Which pairings are prohibited for accessibility or UI reasons?

Initial direction:

- Doubt I never combines punishments; Doubt II permits only light, validated
  overlap.
- Doubt II retains the protective Blackout buffer used by the current game.
- Doubt III permits a limited, explicit set of combinations.
- Deception permits the broadest combinations, including repeated Timer and
  Reverse Entry, while still obeying hard fairness constraints.
- Blackout remains a transition and information punishment, not a repeating event.

The Doubt III allowlist is implemented as specified above. Deception's broader
allowlist remains open until its tuning workshop.

## Hybrid Fairness Standard

The system will not attempt to formally prove every generated game solvable. It
uses a hybrid standard:

1. Hard constraints reject clearly unfair schedules and combinations.
2. Automated simulations estimate difficulty and expose outlier configurations.
3. Human playtests calibrate whether the experience feels strategic rather than
   arbitrary.

Initial outcome calibration targets:

- Deception should approach a 0-2% win rate for average players.
- Experienced Deception players may reach roughly 5-10%.
- Expert players using deliberate lie tracking should remain below a 20% ceiling;
  10-20% is the initial target band, and a lower observed rate is acceptable if
  playtests still find the level strategic rather than arbitrary.

These are tuning targets, not player-facing promises. The team will adjust them as
real playtest evidence accumulates.

Hard fairness constraints include:

- Winning and terminal feedback remain truthful.
- A punishment cannot make valid input technically impossible.
- The server remains authoritative for timeouts and decoded Reverse Entry input.
- A generated schedule cannot violate its preset's repetition or compatibility
  caps.
- The lie planner keeps its plausibility rules and may tell the truth instead of
  forcing an unsafe mutation.
- The highest difficulty may require calculated guesses. Fairness is enforced through
  measurable schedule constraints and simulation rather than an unenforceable proof
  that every game retains a unique rational path.

### Two-tile lie feasibility guard

Coordinated two-tile search must remain deterministic and bounded by the
deception decision budget. It scans the curated alternative-answer corpus once,
aggregates supported mutations, and uses deterministic near-best tie-breaking.
If the deadline arrives after a plausible candidate is found, the best candidate
found so far is used. Truth is returned only when no valid candidate exists or a
hard strategy restriction applies. It must not delay row reveal to force a lie.

## Daily Descent

Daily becomes a four-stage deterministic run:

1. Every player begins at Doubt I.
2. Each stage has a different shared daily answer.
3. Clearing a stage unlocks the next stage for that day's run.
4. Losing any stage ends the entire Daily Descent.
5. Stages cannot be retried until the next 03:00 UTC reset.
6. Clearing Deception completes the full Descent.

The four answers and schedulable challenge blueprints are shared by all players.
Answer selection remains curated and deterministic, with no answer repeated inside
the same Descent.

### Daily run state machine

| State | Meaning | Legal next states |
|---|---|---|
| `unstarted` | No stage has consumed a valid guess | `active`, `expired` |
| `active` | The current stage consumed its first valid guess | `checkpoint`, `failed`, `completed`, `forfeited`, `expired` |
| `checkpoint` | A stage was cleared and the next stage has not been consumed | `active`, `expired` |
| `failed` | The player lost a stage | Terminal until reset |
| `forfeited` | An active stage was interrupted and cannot resume | Terminal until reset |
| `completed` | Deception was cleared | Terminal until reset |
| `expired` | The 03:00 UTC reset passed before the run completed | Terminal for the old puzzle key |

Clearing Doubt I or Doubt II transitions to `checkpoint`. Clearing Doubt III also
transitions to `checkpoint`, with Deception as the next stage. Clearing Deception
transitions directly to `completed`.

### Stage checkpoints

- Completing a stage creates a resumable checkpoint before the next stage begins.
- The result view shows the stage answer and full event breakdown.
- The call to action is stage-aware: **Descend to Doubt II**, **Descend to Doubt
  III**, or **Enter Deception**.
- A player may leave at a stage boundary and continue later that day.
- Opening the next stage does not consume it; its first accepted valid guess does.
- Once a stage has begun, leaving or refreshing forfeits the run under the existing
  Daily interruption rule.

### Reset, concurrency, and versioning

- The server computes the Daily puzzle key and reset boundary. Client clocks never
  select a run or extend one past 03:00 UTC.
- Stage start is transactional and idempotent for one device, run, and stage. Duplicate
  requests return the same unconsumed stage game instead of creating another answer or
  blueprint.
- A run has at most one active stage and one game record for each stage.
- The first accepted valid guess atomically consumes the stage and Daily attempt.
- Requests received after reset cannot mutate the expired run, even if the browser
  still displays it.
- Opening/bootstrap from a new page while a stage is already consumed marks the run
  forfeited; the original active page remains the only supported continuation.
- Multiple-tab and duplicate-request races are resolved by database uniqueness
  constraints and transactions, not last-write-wins behavior.
- Every run is pinned to its answer-list version, preset versions, compatibility
  version, and rules version. A deployment never changes an active run's blueprint.
- Server failure before transaction commit leaves the stage unconsumed. Failure after
  commit returns the same persisted state on an idempotent retry.

### Active-page continuation identity

- Before stage start, the frontend generates an opaque continuation token and keeps it
  only in the active JavaScript page memory. It is never written to local storage,
  session storage, a URL, or analytics.
- Stage-start and guess requests include the token over the same-origin API. The server
  stores only its hash and binds it atomically when the first valid guess consumes the
  stage.
- Repeating a request with the same token is idempotent and may return the already
  persisted result after a network failure.
- A competing tab may view an unconsumed ready stage, but the first valid guess binds
  the stage to one token. Later requests carrying another token are rejected.
- Refreshing destroys the in-memory token. Bootstrap that finds a consumed active stage
  without its continuation token atomically marks the Daily run forfeited.
- The token enforces the interruption contract; it is not an account credential or an
  anti-cheat boundary.

## Infinite Compatibility

- Infinite exposes all four difficulties immediately and allows unrestricted
  replay in the current playtest.
- Infinite uses the same preset definitions as Daily Descent.
- Its answers and challenge blueprints are generated per game rather than from
  the shared daily seed.

## Progress and Future Leaderboards

Persist granular stage outcomes now even though leaderboards are deferred:

- Doubt I cleared.
- Doubt II cleared.
- Doubt III cleared.
- Deception cleared.
- Deepest stage reached that day.
- Full Daily Descent completed.
- Failure stage.
- Preset and rules version.

Lifetime Doubt I totals mostly measure attendance because every deeper clear includes
a Doubt I clear. More meaningful future comparisons include seasonal stage-clear
rates, full-clear counts, current and best full-clear streaks, and deepest-stage
distributions.

A Daily Deception clear is the same event as a full Daily Descent. Direct Deception
wins in Practice or Infinite are tracked separately.

Daily comparisons treat the shared immutable blueprint and identical reactive rules
as the common challenge. Guess-dependent runtime events are consequences of player
strategy, not evidence that two players received different rules. Future leaderboard
copy must not claim that every player experienced identical activated punishments.

## Approaches Considered

### Approach A: Independent probability table

Each preset changes independent lie and punishment percentages. This is the smallest
implementation but cannot reliably guarantee recognizable pressure and becomes
difficult to repair as more punishments are added.

### Approach B: Hidden pressure scheduler

Each preset defines ranges, caps, eligibility, repetition, cooldowns, and combination
permissions. A complete hidden blueprint is created before play. This approach is
selected because it preserves uncertainty while guaranteeing level identity.

### Approach C: Adaptive director

The game schedules pressure dynamically based on player performance. This could
produce tailored games but weakens shared Daily fairness, is harder to test, and can
feel like punishment for playing well. It is deferred.

## Required Data and API Changes

The implementation plan should account for:

- A versioned difficulty-preset definition owned by the backend.
- A persisted challenge blueprint linked to every game and Daily stage.
- A persisted Daily Descent run with stage status and checkpoint state.
- A hash of the active stage's in-memory continuation token after consumption.
- A difficulty identifier on game creation and active game records.
- Bootstrap data describing available presets without exposing hidden schedules.
- Daily bootstrap state describing the current stage, whether the run ended, and
  whether a stage-boundary checkpoint can resume.
- A stage-start operation that atomically binds the correct answer and blueprint.
- Same-origin stage-start and guess contracts that carry the continuation token without
  exposing it in URLs or logs.
- Result data containing the completed stage report and next-stage availability.

The frontend must render backend-provided preset descriptions and must never recreate
probabilities or compatibility rules locally.

## Mechanics References

The authoritative behavior of truthful feedback, lie planning, Reverse Entry, Guess
Timer, and Blackout remains in `DECEPTION_PRODUCT_DECISIONS.md`. This design overrides
only the following former global assumptions:

- Blackout is removed from the easiest preset and begins at Doubt II.
- The one-per-game Timer and Reverse Entry caps apply only to Doubt I and Doubt II.
- The one-active-modifier rule applies to Doubt I and Doubt II; higher presets use an
  explicit compatibility allowlist.
- Daily schedulable events are shared through the stage blueprint. Reactive events
  remain deterministic functions of shared rules and player history.

Invalid guesses never consume a stage or satisfy Reverse Entry. Timer expiry consumes
the currently timed attempt according to the existing server-authoritative rule; a
timer cannot expire before a prior accepted row activates it. A Reverse Entry event
that affected the expired attempt is consumed with that row. The following guess is
reversed only when a distinct event was separately scheduled for it.

## Accessibility Gate

- Every preset supports keyboard, touch, mouse, and controller-equivalent input paths.
- Reduced-motion presentation changes animation, not schedule or outcome.
- Every combined time and input state must pass keyboard, touch, screen-reader,
  focus-order, and reduced-motion testing before public release.
- Any time-pressure opt-out or equivalent replacement must be defined before ranked
  comparisons are introduced. Until then, leaderboard eligibility behavior remains
  unresolved and is not an implementation assumption.

## Verification Strategy

Tests should verify:

- Every generated blueprint obeys the selected preset's lie and punishment caps.
- Doubt I never schedules Blackout.
- Blackout appears no more than once at every level.
- Timer and Reverse Entry repeat only where permitted.
- Same-attempt combinations follow the preset compatibility matrix.
- Identical Daily seeds and guess histories reproduce identical outcomes.
- Different Daily guess histories may produce different reactive outcomes without
  changing the shared answer or schedulable blueprint.
- No answer repeats within one Daily Descent.
- A stage win creates the correct checkpoint and next-stage call to action.
- A stage loss ends the run and blocks every later stage.
- Leaving at a checkpoint is resumable; leaving after stage consumption forfeits.
- Practice permits direct access to every preset.
- Terminal rows stay truthful at every level.
- Structural simulations show no cap, compatibility, determinism, or fairness-guard
  violations. Human win-rate calibration is a separate playtest gate.

### Calibration methodology gate

Before win-rate bands become release criteria, define:

- Deterministic solver/player models for ordinary, experienced, and expert strategy.
- Minimum simulation sample size per preset and preset version.
- Confidence intervals and outlier-blueprint thresholds.
- Human playtest cohort definitions and minimum sample sizes.
- The rule for changing preset versions when observed results miss the target.

Until then, the win-rate numbers in this document are hypotheses and cannot fail a
deterministic unit test.

## Delivery Milestones

### Milestone 0: Numeric tuning gate

Define versioned count ranges, pressure budgets, timer-duration weights, cooldowns,
and the Doubt III/Deception combination allowlists. Engineering may prototype the
pure scheduler types before this gate, but player-facing presets are not ready to
implement without it.

### Milestone 1: Preset foundation and Practice

Define backend-owned preset types, build the deterministic pressure scheduler, migrate
current behavior to `doubt-2@1`, and add Practice selection. Acceptance requires valid
blueprints, unchanged Doubt II regression behavior, and no hidden schedule data in
active API responses.

### Milestone 2: Higher-level mechanics

Add repeated Timer and Reverse Entry support, coordinated two-tile lies, and the
versioned compatibility matrix for Doubt III and Deception. Acceptance requires
bounded lie-planner latency plus cap, overlap, consecutive-event, fallback, and
False Victory recovery tests.

### Milestone 3: Daily Descent

Add the Daily run state machine, four unique deterministic answers, transactional
stage binding, checkpoints, stage-aware results, and reset/concurrency handling.
Acceptance requires all legal state transitions plus duplicate-request, multiple-tab,
and 03:00 UTC boundary tests.

### Milestone 4: Calibration and future competition

Add structural simulation reports and playtest instrumentation. Leaderboard UI,
season definitions, accounts, and Infinite lives remain future work; only granular
stage outcome storage is required earlier.

## Open Questions

- The minimum acceptable expert sample size before adjusting Deception's target band.
- Accessible equivalents for combined time and input-order pressure.
- Seasonal boundaries and scoring if leaderboards are implemented.

## Success Criteria

- Players can correctly rank the four presets by felt intensity without knowing the
  hidden schedules.
- Doubt I remains recognizably Deception while onboarding ordinary Wordle players.
- Doubt II preserves the complete current game identity.
- Doubt III introduces coordinated lies and limited combinations without feeling
  random.
- Deception keeps expert win rate below 20%, with 10-20% as the initial target band.
  A lower rate is acceptable only when playtests still find the level strategic rather
  than arbitrary; average-player wins should remain near zero.
- Daily players receive reproducible, comparable challenges while their own guesses
  still drive reactive outcomes.
- Adding a future punishment requires extending preset data and compatibility rules,
  not rewriting scheduling control flow.

## Implementation Status

Milestones 0 through 3 and preset generation 3 are complete. All four
difficulties are executable in Infinite, and Daily Descent persists its
four-stage run through checkpoints, failure, forfeiture, completion, and the
03:00 UTC reset. Balance is now a playtest calibration question rather than an
architecture gap.

## Next Workshop Assignment

Playtest the full Daily Descent, focusing on stage-to-stage pacing, whether the
checkpoint decision feels meaningful, and whether failure at later stages feels
earned. Calibration and future competition remain Milestone 4 work.
