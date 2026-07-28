import type { FeedbackMarker, GuessResponse } from "../api/types";

export type KeyboardFeedback = Partial<Record<string, FeedbackMarker>>;

const FEEDBACK_RANK: Record<FeedbackMarker, number> = {
  B: 1,
  Y: 2,
  G: 3,
};

export function buildKeyboardFeedback(
  guesses: GuessResponse[],
): KeyboardFeedback {
  const feedback: KeyboardFeedback = {};

  for (const result of guesses) {
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
