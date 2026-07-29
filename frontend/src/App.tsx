import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import { ApiError, api } from "./api/client";
import type { GameMode } from "./api/types";
import { BrandHeader } from "./components/BrandHeader";
import { FeedbackLegend } from "./components/FeedbackLegend";
import { GameBoard } from "./components/GameBoard";
import { GameResult } from "./components/GameResult";
import { HowDeceptionWorks } from "./components/HowDeceptionWorks";
import { Keyboard } from "./components/Keyboard";
import { ModeSelect } from "./components/ModeSelect";
import { buildKeyboardFeedback } from "./game/keyboardState";
import { initialState, reducer } from "./game/state";

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Something unexpected interrupted the game.";
}

function isRecoverableServiceError(error: unknown): boolean {
  return (
    !(error instanceof ApiError) ||
    error.code === "NETWORK_ERROR" ||
    error.code === "SERVICE_UNAVAILABLE"
  );
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [helpOpen, setHelpOpen] = useState(false);
  const [resultOpen, setResultOpen] = useState(false);

  const closeHelp = useCallback(() => setHelpOpen(false), []);
  const closeResult = useCallback(() => setResultOpen(false), []);
  const openHelp = useCallback(() => {
    if (!resultOpen) setHelpOpen(true);
  }, [resultOpen]);

  const loadBootstrap = useCallback(async () => {
    dispatch({ type: "BOOTSTRAP_LOADING" });
    try {
      const bootstrap = await api.bootstrap();
      dispatch({ type: "BOOTSTRAP_SUCCESS", payload: bootstrap });
    } catch (error) {
      dispatch({
        type: "FAILURE",
        scope: "bootstrap",
        message: errorMessage(error),
        recoverable: true,
      });
    }
  }, []);

  useEffect(() => {
    void loadBootstrap();
  }, [loadBootstrap]);

  const startGame = useCallback(async (mode: GameMode) => {
    setHelpOpen(false);
    setResultOpen(false);
    dispatch({ type: "STARTING", mode });
    try {
      const session = await api.startGame(mode);
      dispatch({ type: "START_SUCCESS", payload: session });
    } catch (error) {
      dispatch({
        type: "FAILURE",
        scope: "start",
        message: errorMessage(error),
        recoverable: true,
      });
    }
  }, []);

  const submitGuess = useCallback(async () => {
    if (!state.session || state.phase !== "ready") return;
    if (state.currentGuess.length !== state.session.config.wordLength) {
      dispatch({
        type: "LOCAL_MESSAGE",
        message: `Enter exactly ${state.session.config.wordLength} letters.`,
      });
      return;
    }

    dispatch({ type: "SUBMITTING" });
    try {
      const result = await api.submitGuess(
        state.session.gameId,
        state.currentGuess,
      );
      dispatch({ type: "GUESS_SUCCESS", payload: result });
    } catch (error) {
      dispatch({
        type: "FAILURE",
        scope: "guess",
        message: errorMessage(error),
        recoverable: isRecoverableServiceError(error),
      });
    }
  }, [state.currentGuess, state.phase, state.session]);

  useEffect(() => {
    if (state.phase !== "revealing") return;
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const timer = window.setTimeout(
      () => dispatch({ type: "REVEAL_COMPLETE" }),
      reducedMotion ? 180 : 720,
    );
    return () => window.clearTimeout(timer);
  }, [state.phase]);

  useEffect(() => {
    if (state.phase === "won" || state.phase === "lost") {
      setHelpOpen(false);
      setResultOpen(true);
    }
  }, [state.phase]);

  const onLetter = useCallback((letter: string) => {
    dispatch({ type: "TYPE_LETTER", letter });
  }, []);

  const onBackspace = useCallback(() => {
    dispatch({ type: "BACKSPACE" });
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (helpOpen || resultOpen) return;
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (
        event.target instanceof HTMLElement &&
        event.target.closest("button")
      ) {
        return;
      }
      if (/^[a-zA-Z]$/.test(event.key)) {
        onLetter(event.key);
      } else if (event.key === "Backspace") {
        event.preventDefault();
        onBackspace();
      } else if (event.key === "Enter") {
        event.preventDefault();
        void submitGuess();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [helpOpen, onBackspace, onLetter, resultOpen, submitGuess]);

  const keyboardFeedback = useMemo(
    () => buildKeyboardFeedback(state.guesses),
    [state.guesses],
  );

  if (state.phase === "booting") {
    return (
      <main className="system-screen">
        <p className="system-wordmark">DECEPTION</p>
        <p role="status" aria-live="polite">
          {state.message}
        </p>
      </main>
    );
  }

  if (state.phase === "error" && state.errorScope === "bootstrap") {
    return (
      <main className="system-screen">
        <p className="system-wordmark">DECEPTION</p>
        <h1>Game service unavailable</h1>
        <p role="alert">{state.message}</p>
        <button
          className="mode-button mode-button--primary"
          type="button"
          onClick={() => void loadBootstrap()}
        >
          Retry connection
        </button>
      </main>
    );
  }

  if (
    (state.phase === "selecting" ||
      state.phase === "starting" ||
      (state.phase === "error" && state.errorScope === "start")) &&
    state.bootstrap
  ) {
    return (
      <>
        <ModeSelect
          daily={state.bootstrap.daily}
          busy={state.phase === "starting"}
          message={state.phase === "error" ? state.message : undefined}
          onStart={(mode) => void startGame(mode)}
          onHelp={openHelp}
        />
        {helpOpen ? <HowDeceptionWorks onClose={closeHelp} /> : null}
      </>
    );
  }

  if (!state.session) return null;

  const latest = state.guesses.at(-1);
  const finished = state.phase === "won" || state.phase === "lost";
  const inputDisabled =
    state.phase === "submitting" ||
    state.phase === "revealing" ||
    finished ||
    state.phase === "error";

  return (
    <main className="game-screen">
      <BrandHeader
        mode={state.session.mode}
        onReturn={() => {
          setHelpOpen(false);
          setResultOpen(false);
          void loadBootstrap();
        }}
        onHelp={openHelp}
      />
      <div className="game-stage">
        <GameBoard
          wordLength={state.session.config.wordLength}
          maxGuesses={state.session.config.maxGuesses}
          currentGuess={state.currentGuess}
          guesses={state.guesses}
          revealing={state.phase === "revealing"}
        />

        <div className="game-status-line">
          {state.message ? (
            <p
              className={`game-status ${
                state.errorScope === "guess" ? "game-status--error" : ""
              }`}
              role={state.errorScope === "guess" ? "alert" : "status"}
              aria-live="polite"
            >
              {state.message}
            </p>
          ) : null}
          <p className="guess-progress">
            {state.guesses.length} of {state.session.config.maxGuesses} guesses
          </p>
        </div>

        {state.phase === "error" && state.errorScope === "guess" ? (
          <div className="inline-error-actions">
            <button
              className="text-button"
              type="button"
              onClick={() => void submitGuess()}
            >
              Retry guess
            </button>
            <button
              className="text-button"
              type="button"
              onClick={() => void loadBootstrap()}
            >
              Return to modes
            </button>
          </div>
        ) : null}

        <Keyboard
          feedback={keyboardFeedback}
          disabled={inputDisabled}
          onLetter={onLetter}
          onEnter={() => void submitGuess()}
          onBackspace={onBackspace}
        />
        <FeedbackLegend />

        {finished && !resultOpen ? (
          <button
            className="view-result-button"
            type="button"
            onClick={() => setResultOpen(true)}
          >
            View result
          </button>
        ) : null}

        {finished && resultOpen && latest?.answer ? (
          <GameResult
            mode={state.session.mode}
            status={latest.status === "won" ? "won" : "lost"}
            answer={latest.answer}
            attempt={latest.attempt}
            deception={latest.deception}
            onClose={closeResult}
            onPractice={() => void startGame("practice")}
            onModes={() => {
              setResultOpen(false);
              void loadBootstrap();
            }}
          />
        ) : null}
        {helpOpen && !resultOpen ? (
          <HowDeceptionWorks onClose={closeHelp} />
        ) : null}
      </div>
    </main>
  );
}
