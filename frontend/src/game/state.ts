import type {
  BootstrapResponse,
  GameMode,
  GuessResponse,
  StartGameResponse,
} from "../api/types";

export type AppPhase =
  | "booting"
  | "selecting"
  | "starting"
  | "ready"
  | "submitting"
  | "reversing"
  | "revealing"
  | "won"
  | "lost"
  | "error";

export type ErrorScope = "bootstrap" | "start" | "guess";

export type AppState = {
  phase: AppPhase;
  bootstrap: BootstrapResponse | null;
  session: StartGameResponse | null;
  guesses: GuessResponse[];
  currentGuess: string;
  message: string;
  errorScope: ErrorScope | null;
  lastMode: GameMode | null;
  reverseEntryActive: boolean;
  reverseTransition: {
    enteredGuess: string;
    result: GuessResponse;
  } | null;
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
      payload: GuessResponse;
      enteredGuess: string;
    }
  | { type: "REVERSE_COMPLETE" }
  | { type: "REVEAL_COMPLETE" }
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
  announcement: "",
};

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
    case "GUESS_SUCCESS":
      if (action.payload.reverseEntry?.state === "resolved") {
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
        announcement: "",
      };
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
        };
      }
      if (latest.status === "lost") {
        return {
          ...state,
          phase: "lost",
          message: "",
        };
      }
      return {
        ...state,
        phase: "ready",
        message: "",
        reverseEntryActive:
          latest.reverseEntry?.state === "activated"
            ? true
            : state.reverseEntryActive,
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
