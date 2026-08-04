export type GameMode = "daily" | "practice";
export type GameStatus = "playing" | "won" | "lost";
export type FeedbackMarker = "G" | "Y" | "B";

export type GameConfig = {
  wordLength: number;
  maxGuesses: number;
};

export type DailyInfo = {
  puzzleKey: string;
  availability: "available" | "used";
  resetAt: string;
};

export type DifficultyPresetSummary = {
  presetKey: string;
  name: string;
  rank: number;
  pressure: string;
  description: string;
  available: boolean;
};

export type BootstrapResponse = {
  config: GameConfig;
  daily: DailyInfo;
  presets: DifficultyPresetSummary[];
};

export type StartGameResponse = {
  gameId: string;
  mode: GameMode;
  config: GameConfig;
  puzzleKey?: string;
  preset: DifficultyPresetSummary;
};

export type DeceptionEvent =
  | {
      outcome: "activated";
      kind: "feedbackLie" | "falseVictory";
      scheduledAttempt: number;
      changes: Array<{
        tileIndex: number;
        letter: string;
        truthfulFeedback: FeedbackMarker;
        displayedFeedback: FeedbackMarker;
      }>;
    }
  | {
      outcome: "notActivated";
      scheduledAttempt: number;
      reason: "notReached" | "winningGuess" | "finalAttempt" | "noEligibleLie";
    };

export type DeceptionReveal = {
  events: DeceptionEvent[];
};

export type ActivatedGuessTimer = {
  state: "activated";
  durationSeconds: 10 | 30;
  startsAt: string;
  deadlineAt: string;
};

export type GuessResponse = {
  guess: string;
  feedback: string;
  attempt: number;
  status: GameStatus;
  answer?: string;
  deception?: DeceptionReveal;
  reverseEntry?: {
    state: "activated" | "resolved" | "continued";
  };
  timer?: ActivatedGuessTimer | { state: "completed" };
  blackout?: { state: "activated" };
};

export type TimedOutResponse = {
  timedOut: true;
  attempt: number;
  status: GameStatus;
  answer?: string;
  deception?: DeceptionReveal;
  timer: { state: "expired" };
  nextTimer?: ActivatedGuessTimer;
};

export type AttemptResponse = GuessResponse | TimedOutResponse;

export function isTimedOut(
  result: AttemptResponse,
): result is TimedOutResponse {
  return "timedOut" in result;
}

export type ErrorResponse = {
  error: {
    code: string;
    message: string;
  };
};
