# Deception Product Decisions

**Status:** Implementation reference  
**Last updated:** 2026-07-29
**Source:** Product workshop answers to the seven functional layers

This file is the coding source of truth for Deception. Decisions are locked unless
they are explicitly marked `OPEN`, `WORKING INTERPRETATION`, or `DEFERRED`.

## Decision precedence

When two workshop answers conflict, use this order:

1. The final four priority decisions override earlier answers.
2. A more specific mode decision overrides a general decision.
3. If the answers intentionally vary by game mode, implement the behavior as mode
   configuration instead of hard-coding one global rule.
4. Items marked `OPEN` must not be silently assumed in production code.

## Product definition

Deception is a punishment-survival word game for ordinary Wordle players. The
underlying word evaluation follows familiar Wordle rules, but a deception layer can
alter the feedback and an antagonistic interface can apply timed, visual, and
information-based punishments.

The standard game uses:

- Five-letter answers.
- Six guesses.
- Familiar green, yellow, and gray truth rules.
- A hostile interface layered on top of the truthful word engine.
- Solving the answer word as the final win condition.
- Lie revelation after the game.

The primary fantasy is surviving the antagonistic interface, not purely performing
logical deduction.

## Status key

- `LOCKED`: Approved behavior.
- `WORKING INTERPRETATION`: The answer was ambiguous; this file defines the current
  implementation meaning.
- `OPEN`: A product decision is still required.
- `DEFERRED`: Do not include in the first version.
- `RISK`: Approved direction with a product, legal, accessibility, or technical risk.

---

## Layer 1: Core game contract

| Decision | Status | Implementation requirement |
|---|---|---|
| Primary fantasy | LOCKED | Punishment-survival through an antagonistic interface. |
| Base audience | LOCKED | Ordinary Wordle players, not only expert puzzle players. |
| Standard word length | LOCKED | Five letters. |
| Standard guess limit | LOCKED | Six submitted guesses per game. |
| Truth feedback | LOCKED | Use familiar green, yellow, and gray rules, including normal repeated-letter accounting. |
| Win condition | LOCKED | The player wins by solving the word. Explicitly identifying the lies is not required. |
| Lie interaction | LOCKED | Lies are still revealed after the game, even though identifying them is not required to win. |
| Expected session length | LOCKED | Target the approximate duration of an ordinary Wordle game. Establish a measured target during playtesting. |
| Daily failure | LOCKED | Reveal the deception and end the daily attempt. The same daily puzzle cannot be retried. |
| Play after daily failure | WORKING INTERPRETATION | "Replay and a new word" means starting a different non-daily game, not retrying the failed daily puzzle. |

### Conflict resolved

An earlier answer said the player must both solve the word and identify the lies.
The final priority answer said "solve the word." The final priority answer takes
precedence: solving the word is sufficient.

---

## Layer 2: Deception and fairness

### Locked behavior

- A basic lie changes feedback coloring only.
- A lie never changes a submitted letter or tile position. Letter covering,
  substitutions, and position changes are punishments or modifiers.
- Truthful feedback is calculated before deception.
- One scheduled lie opportunity means one secretly selected row, not one
  guaranteed lying tile.
- Before a game begins, Standard mode schedules two distinct rows 80% of the
  time and one row 20% of the time. Rows are selected from attempts one through
  six.
- If an eligible row is reached, at most one tile may display false feedback.
- The lie may conceal truth or create false certainty.
- Winning guesses and attempt six remain truthful.
- A scheduled row may never be reached or may be required to remain truthful,
  so a game may contain zero, one, or two activated lies.
- Prefer a one-tile mutation backed by a curated alternative answer.
- If no answer-backed mutation exists, allow one constraint-backed false
  yellow on a previously untouched letter when another position could
  plausibly contain it.
- If neither tier can produce a safe mutation, the row stays truthful.
- A failed opportunity is never moved to a later row.
- When two lies activate, they may not alter the same tile position.
- Every scheduled opportunity is explained after the game, whether it
  activated, remained truthful, or was never reached.
- Daily and Practice both use these rules.

### Scope, counts, and visibility

- Standard mode uses a hidden `PER_PUZZLE` schedule containing one or two rows.
- The schedule contains two distinct rows with 80% probability and one row
  with 20% probability.
- Daily uses one shared schedule for the puzzle.
- Practice creates a new schedule per game.
- A scheduled-row count is not the same as an activated-tile count.
- The player is not told whether one or two rows were scheduled.
- Future difficulties may allow a scheduled row to affect multiple tiles.
- The base mode screen does not display a live lie count or warning.
- Player-facing rules say that feedback may lie more than once without
  disclosing the 80/20 schedule distribution.
- The current rules are available through “How Deception Works.”

### Lie planning

- Filter the answer corpus against all previously displayed rows.
- Group the current guess's possible feedback patterns across surviving
  alternative answers.
- Consider only patterns that differ from truth at exactly one tile.
- Reject false all-green feedback.
- Use the hidden seed to select between hiding information and fabricating it.
- Prefer a focused, non-empty decoy group and break ties deterministically.
- If no curated answer supports a mutation, consider only gray-to-yellow
  changes on letters absent from every earlier guess.
- Reject fallback candidates with duplicate-letter ambiguity, no available
  alternate position, or a tile position already used by an earlier lie.
- Rank fallback candidates by accepted-word yellow support and break ties
  deterministically.
- Do not force a lie when neither tier has a safe candidate.

Confirmed-information locks are explicit in the fallback tier and implicit in
the primary tier, where a fixed alternative answer must satisfy the complete
visible history.

---

## Layer 3: Words and content

### Word lists

- Start from a public word-list repository.
- Allow the team to add and remove words over time.
- Maintain separate collections:
  - `validGuesses`: every word the player may submit.
  - `answers`: the curated words that may be selected as solutions.
- `answers` must be a subset of `validGuesses`.

### Allowed answer policy

Do not use the following as answers:

- Plurals.
- Conjugated forms.
- Proper nouns.
- Abbreviations.
- Slang.
- Regional-only spellings.
- Offensive, obscure, or ambiguous words.

American and British spellings belong to the same game, but regional-only terms
should still be excluded from the answer list.

### Important correction

Removing an unsafe or obscure word from `validGuesses` is not sufficient and can
make a puzzle impossible if that word remains an answer.

The required relationship is:

```text
answers ⊆ validGuesses
```

Filtering must happen on the answer list first. A rejected answer may optionally
remain an accepted guess if product policy allows it.

### Daily selection

- Daily answers are selected deterministically from a curated corpus.
- Daily answers are not freely generated.
- An answer must not repeat for at least 365 days.
- Answers do not receive explicit player-facing difficulty ratings.

### Definitions and synonyms

The desired source was identified as Google.

`RISK / OPEN`: Do not scrape Google search-result definitions. Before implementing
hints, select a dictionary or lexical API with documented usage and redistribution
rights.

`DEFERRED`: Definitions, synonyms, and hints are not required for the first version.

---

## Layer 4: Daily and infinite modes

### Daily mode

- Every player receives the same daily answer.
- A new daily puzzle becomes active every 24 hours.
- The reset is based on authoritative server time, not the device clock.
- Changing the device date or timezone must not unlock another daily puzzle.
- The daily puzzle cannot be retried after a loss.
- Daily mode does not have to work offline.
- Interrupted daily games cannot be resumed.
- Opening Daily does not consume the attempt. The first accepted valid guess
  consumes it; invalid and short guesses do not.
- Streaks are stored locally in the initial release.
- Account-based streak synchronization may be added later.

The global reset occurs at `03:00 UTC`.

### Infinite mode

- Infinite mode uses lives.
- Previously played answers should not repeat for the player.
- Interrupted games cannot be resumed.
- A player begins with five lives.
- Lives replenish by one every hour, capped at five.

`OPEN`: Define the remaining life rules:

- When a life is lost.
- Whether a correct answer restores a life.
- What happens when lives reach zero.

### Seeds and sharing

- A shareable seed must be able to reproduce the same word, lies, and modifiers.
- Ordinary daily modifier events may vary by player.

`WORKING INTERPRETATION`: Use separate random seeds:

```text
answerSeed       Same globally for the daily answer.
sessionSeed      Player/session-specific modifier and deception variation.
challengeSeed    Full reproducible state used by a shared challenge link.
```

A challenge link must include or derive the complete `challengeSeed`. Sharing only
the daily date is not enough to reproduce player-specific modifier events.

---

## Layer 5: Difficulty and punishments

The authoritative preset and Daily Descent direction is
[`DIFFICULTY_AND_DAILY_DESCENT_DESIGN.md`](DIFFICULTY_AND_DAILY_DESCENT_DESIGN.md).
It supersedes the former global assumptions about punishment caps, Blackout in the
easiest game, modifier combinations, and Daily schedule sharing. The individual
mechanics below remain authoritative and describe the `doubt-2@1` baseline unless a
preset explicitly overrides their frequency or compatibility.

### Difficulty model

- Expose named difficulty presets to players.
- Internally allow these axes to vary independently:
  - Number or frequency of lies.
  - Time pressure.
  - Modifier selection and intensity.
- Vocabulary difficulty and guess count are not initial difficulty axes.
- Doubt I and `doubt-2@1` allow only one active modifier at a time. Higher presets
  use an explicit compatibility allowlist.
- Modifiers are not announced before the game.
- The player learns about a modifier when it activates.

### Initial punishment categories

- Deceptive tile feedback.
- Covering, hiding, or obscuring letters.
- A timer for the next guess.
- Reversing the required entry order for the next guess.

### First playable punishment: Reverse Entry

`LOCKED`

- After an accepted, nonterminal guess displays four or five absent tiles,
  Reverse Entry activates.
- Every other accepted, nonterminal guess has a 10% activation chance.
- Activation uses displayed feedback, so a lie may cause or prevent it.
- It activates at most once per game and affects the next accepted valid guess.
- The player types the intended word backwards. The server reverses that input,
  validates the decoded word, and stores only the decoded word.
- Invalid input does not consume the punishment. The typed letters remain
  editable and the backwards-entry requirement stays active.
- The previous completed row never changes. The active row shows what the player
  types, then turns into the decoded word before normal feedback appears.
- Daily and Practice use the same behavior.
- Reduced motion replaces the paired tile turn with a short crossfade.
- This implementation is specific to Reverse Entry. It does not introduce a
  generalized punishment engine.

### Second playable punishment: Guess Timer

`LOCKED`

- Each game has a 45% chance to receive one secretly scheduled Guess Timer.
- When a timer is scheduled, it is assigned to one attempt from two through six
  before play begins. The schedule is persisted and never exposed early.
- Scheduled timers are 30 seconds 70% of the time and 10 seconds 30% of the
  time. Across all games, this produces 31.5% with a 30-second timer, 13.5%
  with a 10-second timer, and 55% with no timer.
- The timer activates after the preceding accepted row resolves.
- The server owns the deadline. Slowing the browser, changing tabs, or
  submitting after the visible countdown reaches zero cannot bypass it.
- Invalid and incomplete words do not stop, reset, or consume the timer.
- Expiration consumes the scheduled guess. The board records a row labeled
  `Time expired` without inventing letters or feedback.
- When Timer and Reverse Entry overlap, expiration consumes both events for
  that guess. Reverse Entry affects the following guess only if a distinct
  event was separately scheduled there.
- Expiring on the sixth attempt ends the game as a loss.
- In the current base game, a timer takes priority when it would overlap with
  Reverse Entry. Reverse Entry does not activate for that same guess.
- Timer and Reverse Entry may both occur in one base game, but they do not
  operate on the same guess.
- The guide cannot be opened while a timer is active, and the timer never
  pauses.
- Timer audio is not part of this first implementation.
- This implementation remains specific to Guess Timer. It does not introduce a
  generalized punishment engine.

### Third playable punishment: Blackout

`LOCKED`

- Each game has a 10% chance to receive one secretly scheduled Blackout.
- Once selected, Blackout is assigned to accepted attempt three, four, or five
  with an equal one-third chance for each.
- A correct answer cancels Blackout. Invalid guesses never advance or trigger
  it.
- Blackout begins immediately after the selected row finishes revealing. The
  curtain closes in 160ms, remains fully covered for 120ms, and reopens in 220ms,
  for a 500ms transition.
- While covered, all accumulated rows lose their color feedback and the
  keyboard resets to neutral. Submitted words remain visible on dark tiles.
- Future guesses reveal normally and rebuild keyboard knowledge from that point
  forward.
- When the game ends, the original displayed feedback returns so the player can
  review the board and the lie report.
- Multiple punishments may occur in the same base game. Guess Timer and Reverse
  Entry cannot affect the Blackout attempt or the immediately following
  attempt. They remain eligible elsewhere.
- Reduced motion replaces the moving curtains with a short fade to black and
  back. Input remains locked throughout either transition.

### Failure consequences

- Failing a guess timer consumes the current guess.
- Failing another modifier challenge may remove a piece of evidence.
- Blackout may remove accumulated feedback for the remainder of an active game,
  but the evidence returns after the result.

### Modifier randomization

- Daily Descent shares its immutable schedulable blueprint and derivation seed.
- Reactive events may differ because they are deterministic functions of each
  player's actual guess history.
- Identical Daily guess histories produce identical reactive outcomes.
- Practice and future Infinite games generate a new blueprint per game.
- Shared challenge links use the full challenge seed when exact reproduction is
  required.

### Clarification: input equivalents

"Touch, mobile, keyboard, and controller equivalents" means that a modifier cannot
depend on only one input device.

Examples:

| Interaction | Keyboard | Touch | Controller |
|---|---|---|---|
| Repeated-action QTE | Repeated key press | Repeated screen tap | Repeated face-button press |
| Rearrange scrambled letters | Mouse drag or keyboard selection | Finger drag | Directional selection and confirm |
| Dismiss interruption | Click or key press | Tap | Confirm button |
| Timed guess | Physical keyboard | On-screen keyboard | Controller keyboard/input UI |

Coding requirement:

- Every interactive modifier defines supported input mappings.
- Every motion-heavy modifier defines an accessibility fallback.
- A modifier cannot ship on a platform where its required interaction has no
  workable equivalent.

### Accessibility decision

- Players may disable motion, flashing, audio, or time pressure for accessibility.
- Reduced-motion effects use fades instead of falling, shaking, or scrambling.
- The current product decision restricts some higher difficulty presets when their
  required mechanics are disabled.

`RISK`: Accessibility settings gating higher difficulty may unnecessarily exclude
players. Before competitive or public release, evaluate equivalent accessible
challenges instead of removing access to difficulty levels.

---

## Layer 6: UX, hints, accessibility, and sharing

### Initial board and input

- The full six-row by five-column board is visible and begins with empty tiles.
- The player begins by typing a word.
- The interface communicates the required letter count.
- The initial release uses a five-letter constraint.

### Tutorial

`WORKING INTERPRETATION`: Use a short mode-specific rule card.

Suggested base copy:

> The board is trying to deceive you. Feedback normally follows familiar word-game
> rules, but a clue may be false. Repeated clues can become trustworthy. Solve the
> word in six guesses.

The mode card must separately state:

- Whether lies are per puzzle or per guess.
- Whether the lie budget is visible.
- Which modifier categories the preset can activate.

### Lie-budget display

- Visibility depends on the selected game mode.
- Do not assume the lie count is globally visible.

### Hints

`DEFERRED`: Do not implement hints in the first version.

Possible later behavior:

- A hint may provide a partial definition or partial synonym.
- Hints cost one or more confirmed green clues.

`OPEN`: Define what "costing a green" means:

- Does the green tile become hidden?
- Does it become unconfirmed?
- Is "green" only an abstract currency count?
- Can the player choose which green is spent?

### Accessibility

- Colorblind feedback is handled through accessibility settings.
- Feedback states must not rely on color alone.
- Reduced-motion mode replaces motion effects with fades.

### Post-game result

`WORKING INTERPRETATION` resolving two answers:

- Reveal which feedback was deceptive after a win or loss.
- Do not add a long narrative justification or explanation screen.

### Sharing

`OPEN`: The answer given to the spoiler-free sharing question described a partial
definition, which is a hint rather than a share-result format.

Before implementing social sharing, define whether the result contains:

- Guess count.
- Win or loss.
- Difficulty preset.
- Modifier icons.
- Lie count.
- An emoji grid.
- A challenge seed.

The answer word and exact lie locations should not be included by default.

### Primary product metrics

- Retry rate.
- Daily return rate.

These are the primary metrics for evaluating retention and modifier performance.

---

## Layer 7: Experimental expansion

### Variable word lengths

- Variable word length is an expansion, not an initial-release feature.
- The answer length is hidden.
- The intended eventual range is four to twelve letters.
- Only one major expansion should be developed at a time.
- The justification is increased fun and challenge.

### Experimental modifiers

- Symbol substitution is a modifier, not a separate cipher mode.
- Language changes may use both:
  - Actual translation.
  - Fictional substitution systems.
- QTEs are not optional if disabling them would change competitive results.
- Experimental features must preserve word deduction.
- Fake-ad and reflex mechanics are not limited exclusively to a Chaos mode.

### Clarification: promotion into the standard game

"What promotes a modifier?" means the evidence required before an experimental
modifier becomes part of an ordinary preset.

`WORKING INTERPRETATION`: A modifier is eligible for promotion when playtesting
shows that:

- Players understand what happened and why.
- The modifier does not create an impossible game state.
- The underlying word deduction remains relevant.
- It improves retry rate or daily return.
- It works across the supported input methods.
- It has an acceptable accessibility fallback.
- It does not produce excessive accidental exits or abandoned games.

`OPEN`: Set numerical success and failure thresholds after baseline telemetry exists.

### Modifier compatibility

- Invalid combinations are determined case by case.
- Encode the decisions in a compatibility matrix rather than scattered conditionals.

Suggested shape:

```text
modifierA:
  incompatibleWith:
    - modifierB
    - modifierC
  requires:
    - capabilityX
  accessibleFallback:
    - fallbackModifier
```

---

## Recommended implementation boundaries

Keep these systems separate:

### 1. Truth engine

Responsible only for:

- Answer validation.
- Guess validation.
- Green, yellow, and gray evaluation.
- Repeated-letter accounting.

The truth engine must not know about screen shaking, timers, or visual deception.

### 2. Deception engine

Responsible for:

- Selecting the secretly scheduled rows.
- Transforming one displayed feedback marker.
- Finding patterns supported by plausible alternative answers.
- Preserving complete visible-history consistency.
- Keeping truthful and displayed feedback for post-game reveal.

### 3. Modifier engine

Responsible for:

- Timers.
- Letter covering.
- Scrambling.
- Symbol substitution.
- Language changes.
- QTEs.
- Fake-ad and interruption mechanics.
- Failure consequences.
- Input mappings and accessibility fallbacks.

### 4. Mode configuration

Layer 2A implements only the shared standard behavior for Daily and Practice.
A generalized difficulty or modifier configuration system is deferred until a
second playable difficulty is defined.

---

## Open decisions

### Priority 0 decision status

1. `RESOLVED`: Standard play schedules two distinct `PER_PUZZLE` rows 80% of
   the time and one row 20% of the time.
2. `RESOLVED`: Standard play hides whether one or two rows were scheduled.
3. `RESOLVED`: Basic lies change feedback only. Letter-changing effects are
   punishments or modifiers.
4. `RESOLVED`: The Daily reset occurs at `03:00 UTC`.
5. `PARTIALLY RESOLVED - LATER LAYER`: Infinite mode starts with five lives and
   replenishes one life every hour to a cap of five. Loss and restoration rules
   remain open.

### Priority 1: resolve before the related feature is implemented

1. Select a licensed dictionary/definition source. 
NA for now. If we choose to add hints we'll do this later
2. Define spoiler-free share output.
If we add a share function it will just be a link and show how many you got it in with all the other info just blacked out
3. Define what it means for a hint to cost a green clue.
NA. It might just mean you won't know what a position is for the rest of the game so you can't get it yellow or green or grey even (in our color scheme though not actual those colors)
4. Set modifier-promotion telemetry thresholds.
Circle back to this
5. Decide which accessible equivalents preserve access to higher difficulty levels.
Come to this later, try to maintain high accessibility standards while not making the game easier for them without disqualification from leaderboards
6. Build the first modifier compatibility matrix.
`PARTIALLY RESOLVED`: Doubt I and Doubt II prohibit same-attempt combinations.
Higher-level allowlists and cooldowns remain part of the numeric tuning gate in the
difficulty design.

### Deferred from version one

- Hints and partial definitions.
- Variable answer lengths.
- Four-to-twelve-letter answers.
- Language-changing modifiers.
- Symbol cipher modifiers.
- QTEs.
- Fake-ad interruptions.
- Account-based streak syncing.

---

## Locked MVP summary

The first implementation should include:

1. Five-letter answers.
2. Six guesses.
3. Standard Wordle-style truth evaluation.
4. A separate deception layer.
5. One or two scheduled lie opportunities, with at most one altered tile per
   scheduled row.
6. A truthful winning row.
7. No repeated lie in the same position.
8. Post-game lie revelation.
9. A shared daily answer selected deterministically from a curated list.
10. No daily retry.
11. An infinite mode using lives.
12. Named difficulty presets.
13. Local streak storage.
14. Server-authoritative daily timing.
15. Reduced-motion fades and non-color-only feedback.

Layer 2A's feedback-only lie contract is locked. Standard play uses the hidden
80/20 one-or-two-row schedule above. Future difficulty work must decide when a
row may affect multiple tiles and whether alternate presets expose their
counts.
