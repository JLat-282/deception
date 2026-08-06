import { describe, expect, it } from "vitest";
import type { GuessResponse, StartGameResponse } from "../api/types";
import { type AppState, initialState, reducer } from "./state";

const session: StartGameResponse = {
  gameId: "performance-game",
  mode: "practice",
  config: { wordLength: 5, maxGuesses: 6 },
  preset: {
    presetKey: "deception@3",
    name: "Deception",
    rank: 4,
    pressure: "Extreme",
    description: "An expert survival challenge.",
    available: true,
  },
};

const pressuredGuess: GuessResponse = {
  guess: "slate",
  feedback: "BBGBG",
  attempt: 1,
  status: "playing",
  punishments: [
    { kind: "reverseEntry", state: "activated", effectiveAttempt: 2 },
    { kind: "forcedCommitment", state: "activated", effectiveAttempt: 2 },
    {
      kind: "corruptedHistory",
      state: "activated",
      effectiveAttempt: 2,
      rowAttempt: 1,
    },
    {
      kind: "memoryTax",
      state: "activated",
      effectiveAttempt: 2,
      retainRows: 2,
    },
  ],
};

describe("punishment reducer performance", () => {
  it("resolves a maximum-pressure update within the frontend budget", () => {
    const base: AppState = {
      ...initialState,
      phase: "revealing",
      session,
      guesses: [pressuredGuess],
    };
    const samples: number[] = [];

    for (let index = 0; index < 5_100; index += 1) {
      const started = performance.now();
      reducer(base, { type: "REVEAL_COMPLETE" });
      const elapsed = performance.now() - started;
      if (index >= 100) samples.push(elapsed);
    }

    samples.sort((left, right) => left - right);
    const p99 = samples[Math.floor(samples.length * 0.99)];
    expect(p99).toBeLessThanOrEqual(4);
    expect(samples.at(-1)).toBeLessThanOrEqual(50);
  });
});
