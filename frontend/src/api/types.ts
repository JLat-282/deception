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

export type BootstrapResponse = {
  config: GameConfig;
  daily: DailyInfo;
};

export type StartGameResponse = {
  gameId: string;
  mode: GameMode;
  config: GameConfig;
  puzzleKey?: string;
};

export type DeceptionEvent =
  | {
      outcome: "activated";
      scheduledAttempt: number;
      change: {
        tileIndex: number;
        letter: string;
        truthfulFeedback: FeedbackMarker;
        displayedFeedback: FeedbackMarker;
      };
    }
  | {
      outcome: "notActivated";
      scheduledAttempt: number;
      reason: "notReached" | "winningGuess" | "finalAttempt" | "noEligibleLie";
    };

export type DeceptionReveal = {
  events: DeceptionEvent[];
};

export type GuessResponse = {
  guess: string;
  feedback: string;
  attempt: number;
  status: GameStatus;
  answer?: string;
  deception?: DeceptionReveal;
  reverseEntry?: {
    state: "activated" | "resolved";
  };
};

export type ErrorResponse = {
  error: {
    code: string;
    message: string;
  };
};
