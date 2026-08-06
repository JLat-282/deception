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
  status:
    | "unstarted"
    | "active"
    | "checkpoint"
    | "failed"
    | "forfeited"
    | "completed"
    | "expired";
  currentStage: number;
  clearedStages: number;
  currentPreset?: DifficultyPresetSummary;
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
  dailyStage?: number;
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

export type IntrusionPlacement =
  | "upperLeft"
  | "upperRight"
  | "lowerLeft"
  | "lowerRight";

export type ActivatedIntrusion = {
  state: "activated";
  placement: IntrusionPlacement;
};

export type PunishmentKind =
  | "timer"
  | "reverseEntry"
  | "blackout"
  | "intrusion"
  | "blindEntry"
  | "corruptedHistory"
  | "noRevision"
  | "forcedCommitment"
  | "memoryTax";

export type PunishmentUpdate = {
  kind: PunishmentKind;
  state: "activated" | "resolved" | "continued" | "expired";
  effectiveAttempt: number;
  durationSeconds?: 10 | 30;
  startsAt?: string;
  deadlineAt?: string;
  rowAttempt?: number;
  retainRows?: number;
  placement?: IntrusionPlacement;
};

export type PunishmentReportEvent = {
  kind: PunishmentKind;
  ordinal: number;
  triggerAttempt: number;
  effectiveAttempt: number;
  outcome: "activated" | "missed" | "superseded" | "notReached";
};

export type PunishmentReport = {
  events: PunishmentReportEvent[];
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
  intrusion?: ActivatedIntrusion;
  punishments?: PunishmentUpdate[];
  punishmentReport?: PunishmentReport;
};

export type TimedOutResponse = {
  timedOut: true;
  attempt: number;
  status: GameStatus;
  answer?: string;
  deception?: DeceptionReveal;
  reverseEntry?: {
    state: "resolved" | "continued";
  };
  timer: { state: "expired" };
  nextTimer?: ActivatedGuessTimer;
  punishments?: PunishmentUpdate[];
  punishmentReport?: PunishmentReport;
};

export type InvalidCommitmentResponse = {
  consumed: true;
  reason: "invalidCommitment";
  attemptedGuess: string;
  attempt: number;
  status: GameStatus;
  answer?: string;
  deception?: DeceptionReveal;
  reverseEntry?: {
    state: "resolved" | "continued";
  };
  nextTimer?: ActivatedGuessTimer;
  punishments?: PunishmentUpdate[];
  punishmentReport?: PunishmentReport;
};

export type AttemptResponse =
  | GuessResponse
  | TimedOutResponse
  | InvalidCommitmentResponse;

export function isTimedOut(
  result: AttemptResponse,
): result is TimedOutResponse {
  return "timedOut" in result;
}

export function isInvalidCommitment(
  result: AttemptResponse,
): result is InvalidCommitmentResponse {
  return "reason" in result && result.reason === "invalidCommitment";
}

export type ErrorResponse = {
  error: {
    code: string;
    message: string;
  };
};
