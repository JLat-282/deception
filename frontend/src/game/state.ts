import type {
  ActivatedGuessTimer,
  ActivatedIntrusion,
  AttemptResponse,
  BootstrapResponse,
  GameMode,
  GuessResponse,
  InvalidCommitmentResponse,
  PunishmentKind,
  StartGameResponse,
  TimedOutResponse,
} from "../api/types";
import { isInvalidCommitment, isTimedOut } from "../api/types";

export type AppPhase =
  | "booting"
  | "selecting"
  | "starting"
  | "ready"
  | "submitting"
  | "expiring"
  | "reversing"
  | "revealing"
  | "blackoutClosing"
  | "blackoutOpening"
  | "intrusion"
  | "won"
  | "lost"
  | "error";

export type ErrorScope = "bootstrap" | "start" | "guess" | "timer";

export type AppState = {
  phase: AppPhase;
  bootstrap: BootstrapResponse | null;
  session: StartGameResponse | null;
  guesses: AttemptResponse[];
  currentGuess: string;
  message: string;
  errorScope: ErrorScope | null;
  lastMode: GameMode | null;
  reverseEntryActive: boolean;
  reverseTransition: {
    enteredGuess: string;
    result: GuessResponse;
  } | null;
  timerActive: ActivatedGuessTimer | null;
  pendingTimer: ActivatedGuessTimer | null;
  blackoutCutoffAttempt: number | null;
  intrusionActive: ActivatedIntrusion | null;
  activeInputPunishment: Extract<
    PunishmentKind,
    "blindEntry" | "noRevision" | "forcedCommitment"
  > | null;
  corruptedRowAttempt: number | null;
  memoryTaxActive: boolean;
  memoryTaxRetainRows: number;
  announcement: string;
};

export type Action =
  | { type: "BOOTSTRAP_LOADING" }
  | { type: "BOOTSTRAP_SUCCESS"; payload: BootstrapResponse }
  | { type: "STARTING"; mode: GameMode }
  | { type: "START_SUCCESS"; payload: StartGameResponse }
  | { type: "TYPE_LETTER"; letter: string }
  | { type: "BACKSPACE" }
  | { type: "LOCAL_MESSAGE"; message: string }
  | { type: "SUBMITTING" }
  | {
      type: "GUESS_SUCCESS";
      payload: AttemptResponse;
      enteredGuess: string;
    }
  | { type: "TIMER_EXPIRING" }
  | { type: "TIMEOUT_SUCCESS"; payload: TimedOutResponse }
  | { type: "REVERSE_COMPLETE" }
  | { type: "REVEAL_COMPLETE" }
  | { type: "BLACKOUT_COVERED" }
  | { type: "BLACKOUT_COMPLETE" }
  | { type: "DISMISS_INTRUSION" }
  | {
      type: "FAILURE";
      scope: ErrorScope;
      message: string;
      recoverable?: boolean;
      code?: string;
    };

export const initialState: AppState = {
  phase: "booting",
  bootstrap: null,
  session: null,
  guesses: [],
  currentGuess: "",
  message: "Connecting…",
  errorScope: null,
  lastMode: null,
  reverseEntryActive: false,
  reverseTransition: null,
  timerActive: null,
  pendingTimer: null,
  blackoutCutoffAttempt: null,
  intrusionActive: null,
  activeInputPunishment: null,
  corruptedRowAttempt: null,
  memoryTaxActive: false,
  memoryTaxRetainRows: 2,
  announcement: "",
};

function timeoutRevealState(
  state: AppState,
  payload: TimedOutResponse | InvalidCommitmentResponse,
): AppState {
  return {
    ...state,
    phase: "revealing",
    guesses: [...state.guesses, payload],
    currentGuess: "",
    message: isInvalidCommitment(payload)
      ? "Guess rejected. Attempt consumed."
      : "",
    errorScope: null,
    reverseEntryActive: payload.reverseEntry?.state === "continued",
    timerActive: null,
    pendingTimer: payload.nextTimer ?? null,
    announcement: isInvalidCommitment(payload)
      ? `Guess ${payload.attempt} was rejected and consumed.`
      : `Time expired. Guess ${payload.attempt} was consumed.`,
  };
}

function nextPunishmentState(state: AppState, latest: AttemptResponse) {
  const updates = latest.punishments ?? [];
  const nextAttempt = latest.attempt + 1;
  const input = updates.find(
    (update) =>
      update.state === "activated" &&
      update.effectiveAttempt === nextAttempt &&
      ["blindEntry", "noRevision", "forcedCommitment"].includes(update.kind),
  );
  const corrupted = updates.find(
    (update) =>
      update.kind === "corruptedHistory" && update.state === "activated",
  );
  const memory = updates.find(
    (update) => update.kind === "memoryTax" && update.state === "activated",
  );
  return {
    activeInputPunishment: (input?.kind ??
      null) as AppState["activeInputPunishment"],
    corruptedRowAttempt: corrupted?.rowAttempt ?? null,
    memoryTaxActive: state.memoryTaxActive || Boolean(memory),
    memoryTaxRetainRows: memory?.retainRows ?? state.memoryTaxRetainRows,
  };
}

export function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "BOOTSTRAP_LOADING":
      return {
        ...initialState,
        bootstrap: state.bootstrap,
      };
    case "BOOTSTRAP_SUCCESS":
      return {
        ...initialState,
        phase: "selecting",
        bootstrap: action.payload,
        message: "",
      };
    case "STARTING":
      return {
        ...state,
        phase: "starting",
        lastMode: action.mode,
        message: `Preparing ${action.mode}…`,
        errorScope: null,
      };
    case "START_SUCCESS":
      return {
        ...state,
        phase: "ready",
        session: action.payload,
        guesses: [],
        currentGuess: "",
        message: "",
        errorScope: null,
        reverseEntryActive: false,
        reverseTransition: null,
        timerActive: null,
        pendingTimer: null,
        blackoutCutoffAttempt: null,
        intrusionActive: null,
        activeInputPunishment: null,
        corruptedRowAttempt: null,
        memoryTaxActive: false,
        memoryTaxRetainRows: 2,
        announcement: "",
      };
    case "TYPE_LETTER": {
      if (state.phase !== "ready" || !state.session) return state;
      if (state.currentGuess.length >= state.session.config.wordLength) {
        return state;
      }
      const typedGuess = state.currentGuess + action.letter.toLowerCase();
      return {
        ...state,
        currentGuess: typedGuess,
        message: "",
        errorScope: null,
        announcement:
          state.activeInputPunishment === "blindEntry"
            ? `${typedGuess.length} of ${state.session.config.wordLength} letters entered.`
            : state.announcement,
      };
    }
    case "BACKSPACE": {
      if (state.phase !== "ready") return state;
      if (
        state.activeInputPunishment === "noRevision" &&
        state.currentGuess.length > 0
      ) {
        return {
          ...state,
          message: "Revision is locked.",
          announcement: "Backspace is unavailable for this guess.",
        };
      }
      const shortenedGuess = state.currentGuess.slice(0, -1);
      return {
        ...state,
        currentGuess: shortenedGuess,
        message: "",
        errorScope: null,
        announcement:
          state.activeInputPunishment === "blindEntry" && state.session
            ? `${shortenedGuess.length} of ${state.session.config.wordLength} letters entered.`
            : state.announcement,
      };
    }
    case "LOCAL_MESSAGE":
      return {
        ...state,
        phase: "ready",
        message: action.message,
        errorScope: null,
      };
    case "SUBMITTING":
      return {
        ...state,
        phase: "submitting",
        message: "Checking your guess…",
        errorScope: null,
      };
    case "TIMER_EXPIRING":
      return {
        ...state,
        phase: "expiring",
        message: "",
        errorScope: null,
      };
    case "GUESS_SUCCESS":
      if (isTimedOut(action.payload)) {
        return timeoutRevealState(state, action.payload);
      }
      if (isInvalidCommitment(action.payload)) {
        return timeoutRevealState(state, action.payload);
      }
      if (
        action.payload.reverseEntry?.state === "resolved" ||
        action.payload.reverseEntry?.state === "continued"
      ) {
        return {
          ...state,
          phase: "reversing",
          currentGuess: "",
          message: "",
          errorScope: null,
          reverseEntryActive: false,
          reverseTransition: {
            enteredGuess: action.enteredGuess,
            result: action.payload,
          },
          timerActive:
            action.payload.timer?.state === "completed"
              ? null
              : state.timerActive,
          pendingTimer:
            action.payload.timer?.state === "activated"
              ? action.payload.timer
              : null,
          announcement: `Reverse entry accepted as ${action.payload.guess.toUpperCase()}. Revealing feedback.`,
        };
      }
      return {
        ...state,
        phase: "revealing",
        guesses: [...state.guesses, action.payload],
        currentGuess: "",
        message: "Revealing feedback…",
        errorScope: null,
        timerActive:
          action.payload.timer?.state === "completed"
            ? null
            : state.timerActive,
        pendingTimer:
          action.payload.timer?.state === "activated"
            ? action.payload.timer
            : null,
        announcement: "",
      };
    case "TIMEOUT_SUCCESS":
      return timeoutRevealState(state, action.payload);
    case "REVERSE_COMPLETE":
      if (!state.reverseTransition) return state;
      return {
        ...state,
        phase: "revealing",
        guesses: [...state.guesses, state.reverseTransition.result],
        reverseTransition: null,
        message: "Revealing feedback…",
      };
    case "REVEAL_COMPLETE": {
      const latest = state.guesses.at(-1);
      if (!latest) return state;
      if (latest.status === "won") {
        return {
          ...state,
          phase: "won",
          message: "",
          timerActive: null,
          pendingTimer: null,
          blackoutCutoffAttempt: null,
          corruptedRowAttempt: null,
          memoryTaxActive: false,
          activeInputPunishment: null,
        };
      }
      if (latest.status === "lost") {
        return {
          ...state,
          phase: "lost",
          message: "",
          timerActive: null,
          pendingTimer: null,
          blackoutCutoffAttempt: null,
          corruptedRowAttempt: null,
          memoryTaxActive: false,
          activeInputPunishment: null,
        };
      }
      const punishmentState = nextPunishmentState(state, latest);
      if (
        (isTimedOut(latest) || isInvalidCommitment(latest)) &&
        state.intrusionActive
      ) {
        return {
          ...state,
          phase: "intrusion",
          message: "",
          timerActive: state.pendingTimer,
          pendingTimer: null,
          announcement:
            "Intrusion remains active. Dismiss it before continuing.",
          ...punishmentState,
        };
      }
      if (
        !isTimedOut(latest) &&
        !isInvalidCommitment(latest) &&
        latest.blackout?.state === "activated"
      ) {
        return {
          ...state,
          phase: "blackoutClosing",
          message: "",
          reverseEntryActive: false,
          timerActive: null,
          pendingTimer: state.pendingTimer,
          ...punishmentState,
        };
      }
      const reverseEntryActive =
        !isTimedOut(latest) &&
        !isInvalidCommitment(latest) &&
        (latest.reverseEntry?.state === "activated" ||
          latest.reverseEntry?.state === "continued")
          ? true
          : state.reverseEntryActive;
      if (
        !isTimedOut(latest) &&
        !isInvalidCommitment(latest) &&
        latest.intrusion?.state === "activated"
      ) {
        return {
          ...state,
          phase: "intrusion",
          message: "",
          reverseEntryActive,
          timerActive: state.pendingTimer,
          pendingTimer: null,
          intrusionActive: latest.intrusion,
          announcement:
            "Intrusion. Dismiss the interruption before continuing.",
          ...punishmentState,
        };
      }
      return {
        ...state,
        phase: "ready",
        message: "",
        reverseEntryActive,
        timerActive: state.pendingTimer,
        pendingTimer: null,
        ...punishmentState,
      };
    }
    case "BLACKOUT_COVERED": {
      const latest = state.guesses.at(-1);
      if (
        state.phase !== "blackoutClosing" ||
        !latest ||
        isTimedOut(latest) ||
        isInvalidCommitment(latest)
      ) {
        return state;
      }
      return {
        ...state,
        phase: "blackoutOpening",
        blackoutCutoffAttempt: latest.attempt,
        announcement: "Blackout. Previous feedback has been erased.",
      };
    }
    case "BLACKOUT_COMPLETE": {
      if (state.phase !== "blackoutOpening") return state;
      const latest = state.guesses.at(-1);
      const reverseEntryActive = Boolean(
        latest &&
          !isTimedOut(latest) &&
          !isInvalidCommitment(latest) &&
          (latest.reverseEntry?.state === "activated" ||
            latest.reverseEntry?.state === "continued"),
      );
      if (
        latest &&
        !isTimedOut(latest) &&
        !isInvalidCommitment(latest) &&
        latest.intrusion?.state === "activated"
      ) {
        return {
          ...state,
          phase: "intrusion",
          message: "",
          reverseEntryActive,
          timerActive: state.pendingTimer,
          pendingTimer: null,
          intrusionActive: latest.intrusion,
          announcement:
            "Intrusion. Dismiss the interruption before continuing.",
        };
      }
      return {
        ...state,
        phase: "ready",
        message: "",
        reverseEntryActive,
        timerActive: state.pendingTimer,
        pendingTimer: null,
      };
    }
    case "DISMISS_INTRUSION":
      if (!state.intrusionActive) return state;
      return {
        ...state,
        phase: state.phase === "intrusion" ? "ready" : state.phase,
        intrusionActive: null,
        announcement: "Intrusion dismissed. Play can continue.",
      };
    case "FAILURE":
      if (action.scope === "guess" && action.recoverable !== true) {
        const clearNoRevision =
          state.activeInputPunishment === "noRevision" &&
          action.code === "INVALID_WORD";
        return {
          ...state,
          phase: "ready",
          currentGuess: clearNoRevision ? "" : state.currentGuess,
          message: clearNoRevision
            ? "That guess isn’t accepted."
            : action.message,
          errorScope: action.scope,
        };
      }
      return {
        ...state,
        phase: "error",
        message: action.message,
        errorScope: action.scope,
      };
    default:
      return state;
  }
}
