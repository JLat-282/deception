import type {
  ActivatedGuessTimer,
  AttemptResponse,
  BootstrapResponse,
  GameMode,
  GuessResponse,
  StartGameResponse,
} from "../api/types";
import { isTimedOut } from "../api/types";

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
  | { type: "TIMEOUT_SUCCESS"; payload: AttemptResponse }
  | { type: "REVERSE_COMPLETE" }
  | { type: "REVEAL_COMPLETE" }
  | { type: "BLACKOUT_COVERED" }
  | { type: "BLACKOUT_COMPLETE" }
  | {
      type: "FAILURE";
      scope: ErrorScope;
      message: string;
      recoverable?: boolean;
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
  announcement: "",
};

function timeoutRevealState(
  state: AppState,
  payload: AttemptResponse,
): AppState {
  return {
    ...state,
    phase: "revealing",
    guesses: [...state.guesses, payload],
    currentGuess: "",
    message: "Time expired.",
    errorScope: null,
    timerActive: null,
    pendingTimer: isTimedOut(payload) ? (payload.nextTimer ?? null) : null,
    announcement: `Time expired. Guess ${payload.attempt} was consumed.`,
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
        announcement: "",
      };
    case "TYPE_LETTER":
      if (state.phase !== "ready" || !state.session) return state;
      if (state.currentGuess.length >= state.session.config.wordLength) {
        return state;
      }
      return {
        ...state,
        currentGuess: state.currentGuess + action.letter.toLowerCase(),
        message: "",
        errorScope: null,
      };
    case "BACKSPACE":
      if (state.phase !== "ready") return state;
      return {
        ...state,
        currentGuess: state.currentGuess.slice(0, -1),
        message: "",
        errorScope: null,
      };
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
        message: "Time expired.",
        errorScope: null,
      };
    case "GUESS_SUCCESS":
      if (isTimedOut(action.payload)) {
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
        };
      }
      if (!isTimedOut(latest) && latest.blackout?.state === "activated") {
        return {
          ...state,
          phase: "blackoutClosing",
          message: "",
          reverseEntryActive: false,
          timerActive: null,
          pendingTimer: state.pendingTimer,
        };
      }
      return {
        ...state,
        phase: "ready",
        message: "",
        reverseEntryActive:
          !isTimedOut(latest) &&
          (latest.reverseEntry?.state === "activated" ||
            latest.reverseEntry?.state === "continued")
            ? true
            : state.reverseEntryActive,
        timerActive: state.pendingTimer,
        pendingTimer: null,
      };
    }
    case "BLACKOUT_COVERED": {
      const latest = state.guesses.at(-1);
      if (state.phase !== "blackoutClosing" || !latest || isTimedOut(latest)) {
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
          (latest.reverseEntry?.state === "activated" ||
            latest.reverseEntry?.state === "continued"),
      );
      return {
        ...state,
        phase: "ready",
        message: "",
        reverseEntryActive,
        timerActive: state.pendingTimer,
        pendingTimer: null,
      };
    }
    case "FAILURE":
      if (action.scope === "guess" && action.recoverable !== true) {
        return {
          ...state,
          phase: "ready",
          message: action.message,
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
