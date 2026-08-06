import { describe, expect, it } from "vitest";
import type { BootstrapResponse, StartGameResponse } from "../api/types";
import { isInvalidCommitment, isTimedOut } from "../api/types";
import { initialState, reducer } from "./state";

const bootstrap: BootstrapResponse = {
  config: { wordLength: 5, maxGuesses: 6 },
  daily: {
    puzzleKey: "2026-07-28",
    availability: "available",
    resetAt: "2026-07-29T03:00:00Z",
    status: "unstarted",
    currentStage: 1,
    clearedStages: 0,
  },
  presets: [],
};

const session: StartGameResponse = {
  gameId: "game-1",
  mode: "practice",
  config: bootstrap.config,
  preset: {
    presetKey: "doubt-2@1",
    name: "Doubt II",
    rank: 2,
    pressure: "Standard",
    description: "The complete standard Deception experience.",
    available: true,
  },
};

describe("app state machine", () => {
  it("moves from bootstrap through a playable session", () => {
    const selecting = reducer(initialState, {
      type: "BOOTSTRAP_SUCCESS",
      payload: bootstrap,
    });
    const starting = reducer(selecting, {
      type: "STARTING",
      mode: "practice",
    });
    const ready = reducer(starting, {
      type: "START_SUCCESS",
      payload: session,
    });
    const typed = reducer(ready, { type: "TYPE_LETTER", letter: "C" });

    expect(selecting.phase).toBe("selecting");
    expect(starting.phase).toBe("starting");
    expect(ready.phase).toBe("ready");
    expect(typed.currentGuess).toBe("c");
  });

  it("announces Blind Entry character counts without reading letters", () => {
    const ready = {
      ...initialState,
      phase: "ready" as const,
      bootstrap,
      session,
      activeInputPunishment: "blindEntry" as const,
    };
    const typed = reducer(ready, { type: "TYPE_LETTER", letter: "C" });
    const typedAgain = reducer(typed, { type: "TYPE_LETTER", letter: "R" });
    const deleted = reducer(typedAgain, { type: "BACKSPACE" });

    expect(typed.announcement).toBe("1 of 5 letters entered.");
    expect(typedAgain.announcement).toBe("2 of 5 letters entered.");
    expect(deleted.announcement).toBe("1 of 5 letters entered.");
    expect(typed.announcement).not.toContain("C");
  });

  it("reveals and finishes a winning guess", () => {
    const ready = {
      ...initialState,
      phase: "ready" as const,
      bootstrap,
      session,
      message: "Type a five-letter word.",
    };
    const revealing = reducer(ready, {
      type: "GUESS_SUCCESS",
      enteredGuess: "crane",
      payload: {
        guess: "crane",
        feedback: "GGGGG",
        attempt: 1,
        status: "won",
        answer: "crane",
      },
    });
    const won = reducer(revealing, { type: "REVEAL_COMPLETE" });

    expect(revealing.phase).toBe("revealing");
    expect(won.phase).toBe("won");
    expect(won.message).toBe("");
  });

  it("holds a reversed entry for normalization before feedback", () => {
    const ready = {
      ...initialState,
      phase: "ready" as const,
      bootstrap,
      session,
      reverseEntryActive: true,
    };
    const reversing = reducer(ready, {
      type: "GUESS_SUCCESS",
      enteredGuess: "enarc",
      payload: {
        guess: "crane",
        feedback: "GGGGG",
        attempt: 2,
        status: "won",
        answer: "crane",
        reverseEntry: { state: "resolved" },
      },
    });
    const revealing = reducer(reversing, { type: "REVERSE_COMPLETE" });

    expect(reversing.phase).toBe("reversing");
    expect(reversing.guesses).toEqual([]);
    expect(reversing.reverseEntryActive).toBe(false);
    expect(reversing.announcement).toContain("Reverse entry accepted as CRANE");
    expect(revealing.phase).toBe("revealing");
    const revealed = revealing.guesses[0];
    expect(
      revealed && !isTimedOut(revealed) && !isInvalidCommitment(revealed)
        ? revealed.guess
        : null,
    ).toBe("crane");
  });

  it("activates a scheduled timer and records a consumed timeout row", () => {
    const ready = {
      ...initialState,
      phase: "ready" as const,
      bootstrap,
      session,
      reverseEntryActive: true,
    };
    const firstReveal = reducer(ready, {
      type: "GUESS_SUCCESS",
      enteredGuess: "slate",
      payload: {
        guess: "slate",
        feedback: "BBGBG",
        attempt: 1,
        status: "playing",
        timer: {
          state: "activated",
          durationSeconds: 10,
          startsAt: "2026-07-28T12:00:01Z",
          deadlineAt: "2026-07-28T12:00:11Z",
        },
      },
    });
    const timed = reducer(firstReveal, { type: "REVEAL_COMPLETE" });
    const expiring = reducer(timed, { type: "TIMER_EXPIRING" });
    const timeoutReveal = reducer(expiring, {
      type: "TIMEOUT_SUCCESS",
      payload: {
        timedOut: true,
        attempt: 2,
        status: "playing",
        reverseEntry: { state: "resolved" },
        timer: { state: "expired" },
      },
    });
    const resumed = reducer(timeoutReveal, { type: "REVEAL_COMPLETE" });

    expect(timed.timerActive?.durationSeconds).toBe(10);
    expect(expiring.phase).toBe("expiring");
    expect(timeoutReveal.guesses).toHaveLength(2);
    expect(timeoutReveal.message).toBe("");
    const consumedAttempt = timeoutReveal.guesses[1];
    expect(consumedAttempt ? isTimedOut(consumedAttempt) : false).toBe(true);
    expect(resumed.phase).toBe("ready");
    expect(resumed.timerActive).toBeNull();
    expect(resumed.reverseEntryActive).toBe(false);
  });

  it("starts a consecutive timer after a timed turn is consumed", () => {
    const ready = {
      ...initialState,
      phase: "ready" as const,
      bootstrap,
      session,
      reverseEntryActive: true,
      timerActive: {
        state: "activated" as const,
        durationSeconds: 10 as const,
        startsAt: "2026-07-28T12:00:01Z",
        deadlineAt: "2026-07-28T12:00:11Z",
      },
    };
    const timeoutReveal = reducer(ready, {
      type: "TIMEOUT_SUCCESS",
      payload: {
        timedOut: true,
        attempt: 2,
        status: "playing",
        reverseEntry: { state: "continued" },
        timer: { state: "expired" },
        nextTimer: {
          state: "activated",
          durationSeconds: 30,
          startsAt: "2026-07-28T12:00:12Z",
          deadlineAt: "2026-07-28T12:00:42Z",
        },
      },
    });
    const resumed = reducer(timeoutReveal, { type: "REVEAL_COMPLETE" });

    expect(resumed.phase).toBe("ready");
    expect(resumed.timerActive?.durationSeconds).toBe(30);
    expect(resumed.reverseEntryActive).toBe(true);
  });

  it("runs Blackout after feedback and erases information through that row", () => {
    const ready = {
      ...initialState,
      phase: "ready" as const,
      bootstrap,
      session,
      guesses: [
        {
          guess: "slate",
          feedback: "BBGBG",
          attempt: 1,
          status: "playing" as const,
        },
        {
          guess: "fight",
          feedback: "BBBBB",
          attempt: 2,
          status: "playing" as const,
        },
      ],
    };
    const revealing = reducer(ready, {
      type: "GUESS_SUCCESS",
      enteredGuess: "picky",
      payload: {
        guess: "picky",
        feedback: "BBBBB",
        attempt: 3,
        status: "playing",
        blackout: { state: "activated" },
        reverseEntry: { state: "activated" },
        timer: {
          state: "activated",
          durationSeconds: 30,
          startsAt: "2026-07-28T12:00:02Z",
          deadlineAt: "2026-07-28T12:00:32Z",
        },
      },
    });
    const closing = reducer(revealing, { type: "REVEAL_COMPLETE" });
    const opening = reducer(closing, { type: "BLACKOUT_COVERED" });
    const resumed = reducer(opening, { type: "BLACKOUT_COMPLETE" });

    expect(closing.phase).toBe("blackoutClosing");
    expect(closing.blackoutCutoffAttempt).toBeNull();
    expect(opening.phase).toBe("blackoutOpening");
    expect(opening.blackoutCutoffAttempt).toBe(3);
    expect(opening.announcement).toBe(
      "Blackout. Previous feedback has been erased.",
    );
    expect(resumed.phase).toBe("ready");
    expect(resumed.reverseEntryActive).toBe(true);
    expect(resumed.timerActive?.durationSeconds).toBe(30);
  });

  it("blocks play for Intrusion while keeping an activated Timer live", () => {
    const ready = {
      ...initialState,
      phase: "ready" as const,
      bootstrap,
      session,
    };
    const revealing = reducer(ready, {
      type: "GUESS_SUCCESS",
      enteredGuess: "fight",
      payload: {
        guess: "fight",
        feedback: "BBBBB",
        attempt: 2,
        status: "playing",
        intrusion: { state: "activated", placement: "upperRight" },
        reverseEntry: { state: "activated" },
        timer: {
          state: "activated",
          durationSeconds: 10,
          startsAt: "2026-07-28T12:00:01Z",
          deadlineAt: "2026-07-28T12:00:11Z",
        },
      },
    });
    const intruded = reducer(revealing, { type: "REVEAL_COMPLETE" });
    const ignoredType = reducer(intruded, {
      type: "TYPE_LETTER",
      letter: "c",
    });
    const resumed = reducer(intruded, { type: "DISMISS_INTRUSION" });

    expect(intruded.phase).toBe("intrusion");
    expect(intruded.intrusionActive?.placement).toBe("upperRight");
    expect(intruded.timerActive?.durationSeconds).toBe(10);
    expect(intruded.reverseEntryActive).toBe(true);
    expect(ignoredType.currentGuess).toBe("");
    expect(resumed.phase).toBe("ready");
    expect(resumed.timerActive?.durationSeconds).toBe(10);
    expect(resumed.intrusionActive).toBeNull();
  });

  it("finishes Blackout before presenting an overlapping Intrusion", () => {
    const revealing = reducer(
      {
        ...initialState,
        phase: "ready" as const,
        bootstrap,
        session,
      },
      {
        type: "GUESS_SUCCESS",
        enteredGuess: "picky",
        payload: {
          guess: "picky",
          feedback: "BBBBB",
          attempt: 3,
          status: "playing",
          blackout: { state: "activated" },
          intrusion: { state: "activated", placement: "lowerLeft" },
        },
      },
    );
    const closing = reducer(revealing, { type: "REVEAL_COMPLETE" });
    const opening = reducer(closing, { type: "BLACKOUT_COVERED" });
    const intruded = reducer(opening, { type: "BLACKOUT_COMPLETE" });

    expect(closing.phase).toBe("blackoutClosing");
    expect(opening.phase).toBe("blackoutOpening");
    expect(intruded.phase).toBe("intrusion");
    expect(intruded.intrusionActive?.placement).toBe("lowerLeft");
  });

  it("keeps Intrusion active when a background Timer expires", () => {
    const intruded = {
      ...initialState,
      phase: "intrusion" as const,
      bootstrap,
      session,
      intrusionActive: {
        state: "activated" as const,
        placement: "upperLeft" as const,
      },
      timerActive: {
        state: "activated" as const,
        durationSeconds: 10 as const,
        startsAt: "2026-07-28T12:00:01Z",
        deadlineAt: "2026-07-28T12:00:11Z",
      },
    };
    const expiring = reducer(intruded, { type: "TIMER_EXPIRING" });
    const revealing = reducer(expiring, {
      type: "TIMEOUT_SUCCESS",
      payload: {
        timedOut: true,
        attempt: 3,
        status: "playing",
        timer: { state: "expired" },
      },
    });
    const stillIntruded = reducer(revealing, { type: "REVEAL_COMPLETE" });

    expect(expiring.intrusionActive).toEqual(intruded.intrusionActive);
    expect(revealing.intrusionActive).toEqual(intruded.intrusionActive);
    expect(stillIntruded.phase).toBe("intrusion");
    expect(stillIntruded.intrusionActive).toEqual(intruded.intrusionActive);
  });

  it("activates Blind Entry for the next guess and clears it afterward", () => {
    const revealing = {
      ...initialState,
      phase: "revealing" as const,
      bootstrap,
      session,
      guesses: [
        {
          guess: "slate",
          feedback: "BBBBB",
          attempt: 1,
          status: "playing" as const,
          punishments: [
            {
              kind: "blindEntry" as const,
              state: "activated" as const,
              effectiveAttempt: 2,
            },
          ],
        },
      ],
    };
    const ready = reducer(revealing, { type: "REVEAL_COMPLETE" });
    const typed = reducer(ready, { type: "TYPE_LETTER", letter: "c" });

    expect(ready.activeInputPunishment).toBe("blindEntry");
    expect(typed.currentGuess).toBe("c");
  });

  it("locks Backspace during No Revision", () => {
    const locked = {
      ...initialState,
      phase: "ready" as const,
      bootstrap,
      session,
      activeInputPunishment: "noRevision" as const,
      currentGuess: "cr",
    };
    const next = reducer(locked, { type: "BACKSPACE" });
    expect(next.currentGuess).toBe("cr");
    expect(next.message).toBe("Revision is locked.");
  });
});
