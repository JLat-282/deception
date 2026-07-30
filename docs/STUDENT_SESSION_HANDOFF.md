# Deception Student Punishment Sprint

**First session:** Thursday, 2026-07-30

**Follow-up session:** Monday

**Goal:** Let students choose, plan, and begin implementing one punishment

## Selected feature: Reverse Entry

The group selected Reverse Entry. This decision replaces the selection exercise
below as the active implementation target.

- Four or five displayed gray tiles guarantee activation.
- Every other accepted, nonterminal guess has a 10% activation chance.
- Displayed feedback controls activation, including any lie on that row.
- It can activate only once per game.
- The player must type the next intended word backwards.
- Invalid reversed input remains editable and does not clear the punishment.
- On acceptance, the typed row turns into the decoded word before feedback.
- The completed row that triggered it stays unchanged.
- Daily and Practice use the same rule.
- Reduced motion uses a crossfade.
- No generalized modifier system and no second punishment are included.

## What happens tomorrow

Tomorrow is a complete product-and-development sprint:

1. Play the current game.
2. Discuss what makes Deception interesting, fair, tense, or frustrating.
3. Review a short menu of possible punishments.
4. Choose exactly one punishment.
5. Lock its most important rules.
6. Write a compact implementation plan.
7. Build as much of the playable feature as time allows.
8. Leave a precise implementation handoff for weekend completion.

The feature does not have to be fully polished tomorrow. It must end the session
with either a playable vertical slice or a clear, partially implemented path to
one.

## Current game

The build already includes:

- Standard five-letter, six-guess word evaluation.
- Daily and unlimited Practice modes.
- One or two secretly selected rows.
- Answer-backed one-tile feedback lies.
- Constraint-backed false-yellow fallback lies.
- Truthful winning and sixth rows.
- Postgame lie disclosure.
- Consistent reveal timing.

The next feature should introduce the first punishment that is separate from a
feedback lie.

## Guided questions after play

Use specific moments from the games students just played.

1. When did the game actually change your next guess?
2. What separates a hostile game from an unfair game?
3. Should a punishment attack time, memory, information, attention, or
   confidence?
4. What information can the game take away without making the word impossible
   to solve?
5. How should a player know that something strange is an intentional
   punishment rather than a bug?
6. Should punishments create a cost, create tension, or force a different
   action?
7. How often could the same punishment occur before it becomes annoying?
8. What would make you want to replay after being punished?

End the discussion by writing three principles the selected punishment must
follow.

## Punishment menu

Students may choose one of the following. The group may adjust the exact
presentation and rules after choosing, but may not combine two punishments.

### 1. Guess Timer

After a row resolves, the player receives a limited amount of time to submit
the next valid guess.

Possible intensities:

- 30 seconds: pressure without demanding reflexes.
- 20 seconds: meaningful urgency.
- 10 seconds: aggressive difficulty.

Questions to decide:

- When can the timer activate?
- Does it activate once per game or by probability after eligible guesses?
- Is the duration fixed or selected from multiple intensities?
- How does the game represent the consumed guess when time expires?
- Does an invalid word stop the timer?
- Does opening help pause the timer?
- What is the accessible alternative when time pressure is disabled?

Delivery level: **Moderate**

Primary risk: timeout behavior needs a precise frontend and backend contract so
refreshing or slowing the browser cannot bypass it.

The current product decision says an expired guess timer normally consumes the
current guess. Students may challenge that decision, but they must explicitly
replace it rather than leaving timeout behavior undefined.

### 2. Evidence Veil

The game temporarily covers one previously revealed row.

Possible variants:

- Hide the row but preserve its feedback color.
- Hide the feedback color but preserve the row.
- Hide both the row and feedback.

Questions to decide:

- Which previous rows are eligible?
- Can confirmed green evidence be covered?
- Can a lying row be covered?
- Does the veil last until the next accepted guess, for a duration, or until
  the game ends?
- How does the evidence return?
- How is the hidden row announced to assistive technology?

Delivery level: **Low**

Primary risk: hiding too much information can feel arbitrary or make the puzzle
effectively impossible.

### 3. Keyboard Amnesia

The on-screen keyboard temporarily forgets some or all accumulated feedback
colors while remaining fully usable.

Possible variants:

- Reset every key to its neutral appearance for one guess.
- Hide only absent-letter markings.
- Hide the keyboard feedback until another valid guess is submitted.

Questions to decide:

- Does the board retain the original evidence?
- Which keyboard information disappears?
- How long does the effect last?
- Does it affect physical-keyboard users fairly?
- How does the keyboard restore its state?

Delivery level: **Low**

Primary risk: it may be too weak when the full board remains visible.

### 4. Row Scramble

The visible positions of letters in one completed row are temporarily
rearranged. The stored guess and its real positions do not change.

Questions to decide:

- Are letters, feedback colors, or entire tiles rearranged?
- Which rows are eligible?
- How long does the scramble last?
- Can the player manually restore it?
- What replaces the movement under reduced motion?
- How does a screen reader receive the original information?

Delivery level: **Moderate**

Primary risk: the distinction between a visual punishment and altered game data
must remain unmistakable.

### 5. Intrusion

An interruption covers part of the board and must be dismissed before play
continues.

Possible variants:

- A single dismiss button.
- A short sequence of two or three prompts.
- A movable obstruction that blocks different evidence.

Questions to decide:

- Does the timer or game pause during the interruption?
- What inputs dismiss it on keyboard, touch, and mouse?
- How frequently may it appear?
- Does it create a meaningful word-game challenge or only an annoyance?

Delivery level: **Low**

Primary risk: it can become disconnected from word deduction and feel like a
generic pop-up.

## Recommendation during selection

Use the menu to make a choice, not to begin five designs.

If the group prioritizes:

- **Tension:** choose Guess Timer.
- **Memory and uncertainty:** choose Evidence Veil.
- **Fast implementation:** choose Keyboard Amnesia.
- **Visual disruption:** choose Row Scramble.
- **Attention and interruption:** choose Intrusion.

The timer is a valid choice. A first prototype can test one duration such as 30
seconds before adding 20-second, 10-second, or probability variations.

## Rules that apply to every choice

- Only one punishment is implemented.
- Only one modifier may be active at a time.
- The punishment is not announced before the game.
- The player is told when it activates.
- The answer must remain solvable.
- Winning and loss rules remain unchanged unless the selected punishment
  specifically requires a locked failure consequence.
- Daily and Practice behavior must be stated explicitly.
- Keyboard, touch, and mouse behavior must be defined.
- Reduced-motion and assistive-technology behavior must be included.
- Activation and randomness must be reproducible through a test seed.
- The first implementation should activate no more than once per game unless
  the students provide a strong reason otherwise.
- No generalized modifier framework is required.

## Rapid selection process

1. Give each punishment a two-minute student pitch.
2. Remove any option the group believes would be unfair or uninteresting.
3. Vote on the remaining options.
4. Give the top choice a five-minute feasibility challenge.
5. If it survives, lock it. If it fails, move immediately to the second choice.

The feature is selected when the group can answer:

> What does this punishment make the player feel or do that the current game
> does not?

## Compact feature plan

Complete this before coding. Keep it short enough to finish in approximately 30
minutes.

```markdown
# [Punishment Name] Plan

## Experience
One paragraph describing what the player experiences and why it belongs in
Deception.

## Locked rules
- Activation:
- Probability or schedule:
- Intensity:
- Duration:
- Failure or completion consequence:
- Cancellation conditions:
- Daily behavior:
- Practice behavior:
- Accessibility behavior:

## Player states
List what the player sees before activation, during the punishment, after it
ends, and when something fails.

## Backend
List required scheduling, persistence, API, clock, and deterministic-seed
changes.

## Frontend
List required state, components, copy, animation, responsive, input, and
accessibility changes.

## Edge cases
Cover winning guesses, final guesses, invalid guesses, refresh, API failure,
help/result dialogs, and interaction with a lying row.

## Acceptance criteria
Write observable pass/fail conditions.

## Focused tests
List only the tests needed to establish the core contract.

## Cut line
Identify every optional variation that can be removed while preserving one
playable version.
```

## Implementation sprint

After the plan is reviewed, divide the work:

### Product and review

- Keep the locked rules visible.
- Answer implementation questions immediately.
- Reject behavior that silently changes the approved scope.
- Prepare test scenarios for the first playable version.

### Backend

- Add the smallest required persisted state.
- Add deterministic activation and selection.
- Expose only player-visible modifier state.
- Add fixed test controls.
- Write focused logic and API tests.

### Frontend

- Add the activation, active, completion, and error states.
- Support keyboard, mouse, touch, and narrow screens.
- Add status announcements and reduced-motion behavior.
- Preserve existing game and result flows.

### Integration and testing

- Get one complete path playable as early as possible.
- Test interaction with truthful and lying rows.
- Test the selected punishment's main failure or completion path.
- Record defects and missing decisions for the weekend handoff.

## Definition of success tomorrow

The session succeeds if it produces:

- One selected punishment.
- One approved compact plan.
- Locked first-version rules.
- A started implementation in the shared repository.
- At least one working slice, even if it uses deterministic test settings.
- A list separating blocking work from optional polish.
- A handoff clear enough to continue without guessing what students intended.

The session does not fail because every animation or probability option is not
finished.

## Weekend continuation

Weekend work should:

- Follow the approved student plan.
- Preserve the students' locked product decisions.
- Complete the smallest end-to-end version first.
- Use the cut line instead of expanding scope.
- Run focused regression, build, and accessibility checks.
- Record any necessary deviation and why it was required.
- Leave a stable build ready for Monday.

Do not add another punishment over the weekend.

## Monday student review

Students will:

1. Play the developed feature without being told every implementation detail.
2. Compare it with the plan they approved.
3. Identify implementation defects separately from product-rule problems.
4. Test the main edge cases and accessibility behavior.
5. Decide which corrections are required and which are optional.
6. Approve the corrected feature or return it with a precise revision list.

Use this correction format:

```text
Observed behavior:
Expected behavior from the plan:
Type: BUG / PRODUCT CHANGE / POLISH
Required correction:
Priority: BLOCKING / IMPORTANT / OPTIONAL
```

## Not part of this sprint

- A second punishment.
- Multiple simultaneous modifiers.
- A generalized difficulty system.
- Infinite Mode lives.
- Permanent evidence deletion.
- Hints or definitions.
- Variable word lengths.
- Accounts, sharing, leaderboards, or analytics.
- Public deployment unless it is separately required to let students test.
