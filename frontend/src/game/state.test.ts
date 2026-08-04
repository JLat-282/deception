import { describe, expect, it } from "vitest";
import type { BootstrapResponse, StartGameResponse } from "../api/types";
import { isTimedOut } from "../api/types";
import { initialState, reducer } from "./state";

const bootstrap: BootstrapResponse = {
  config: { wordLength: 5, maxGuesses: 6 },
  daily: {
    puzzleKey: "2026-07-28",
    availability: "available",
    resetAt: "2026-07-29T03:00:00Z",
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
    expect(revealed && !isTimedOut(revealed) ? revealed.guess : null).toBe(
      "crane",
    );
  });

  it("activates a scheduled timer and records a consumed timeout row", () => {
    const ready = {
      ...initialState,
      phase: "ready" as const,
      bootstrap,
      session,
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
        timer: { state: "expired" },
      },
    });
    const resumed = reducer(timeoutReveal, { type: "REVEAL_COMPLETE" });

    expect(timed.timerActive?.durationSeconds).toBe(10);
    expect(expiring.phase).toBe("expiring");
    expect(timeoutReveal.guesses).toHaveLength(2);
    const consumedAttempt = timeoutReveal.guesses[1];
    expect(consumedAttempt ? isTimedOut(consumedAttempt) : false).toBe(true);
    expect(resumed.phase).toBe("ready");
    expect(resumed.timerActive).toBeNull();
  });

  it("starts a consecutive timer after a timed turn is consumed", () => {
    const ready = {
      ...initialState,
      phase: "ready" as const,
      bootstrap,
      session,
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
});
