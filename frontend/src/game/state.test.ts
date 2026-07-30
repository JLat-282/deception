import { describe, expect, it } from "vitest";
import type { BootstrapResponse, StartGameResponse } from "../api/types";
import { initialState, reducer } from "./state";

const bootstrap: BootstrapResponse = {
  config: { wordLength: 5, maxGuesses: 6 },
  daily: {
    puzzleKey: "2026-07-28",
    availability: "available",
    resetAt: "2026-07-29T03:00:00Z",
  },
};

const session: StartGameResponse = {
  gameId: "game-1",
  mode: "practice",
  config: bootstrap.config,
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
    expect(reversing.announcement).toContain(
      "Reverse entry accepted as CRANE",
    );
    expect(revealing.phase).toBe("revealing");
    expect(revealing.guesses[0]?.guess).toBe("crane");
  });
});
