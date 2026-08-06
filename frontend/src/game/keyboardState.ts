import type { AttemptResponse, FeedbackMarker } from "../api/types";
import { isInvalidCommitment, isTimedOut } from "../api/types";

export type KeyboardFeedback = Partial<Record<string, FeedbackMarker>>;

const FEEDBACK_RANK: Record<FeedbackMarker, number> = {
  B: 1,
  Y: 2,
  G: 3,
};

export function buildKeyboardFeedback(
  guesses: AttemptResponse[],
  afterAttempt: number | null = null,
): KeyboardFeedback {
  const feedback: KeyboardFeedback = {};

  for (const result of guesses) {
    if (afterAttempt !== null && result.attempt <= afterAttempt) continue;
    if (isTimedOut(result) || isInvalidCommitment(result)) continue;
    for (let index = 0; index < result.guess.length; index += 1) {
      const letter = result.guess[index].toUpperCase();
      const next = result.feedback[index] as FeedbackMarker;
      const current = feedback[letter];
      if (!current || FEEDBACK_RANK[next] > FEEDBACK_RANK[current]) {
        feedback[letter] = next;
      }
    }
  }

  return feedback;
}
