import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";
import { ApiError, api } from "./api/client";
import type { GameMode } from "./api/types";
import { BlackoutCurtain } from "./components/BlackoutCurtain";
import { BrandHeader } from "./components/BrandHeader";
import { FeedbackLegend } from "./components/FeedbackLegend";
import { GameBoard } from "./components/GameBoard";
import { GameResult } from "./components/GameResult";
import { GuessTimer } from "./components/GuessTimer";
import { HowDeceptionWorks } from "./components/HowDeceptionWorks";
import { Intrusion } from "./components/Intrusion";
import { Keyboard } from "./components/Keyboard";
import { ModeSelect } from "./components/ModeSelect";
import { PracticeDifficultySelect } from "./components/PracticeDifficultySelect";
import { buildKeyboardFeedback } from "./game/keyboardState";
import { waitForRevealStart } from "./game/revealTiming";
import { initialState, reducer } from "./game/state";

export const GUIDE_SEEN_STORAGE_KEY = "deception-guide-seen-v1";

function hasSeenGuide(): boolean {
  try {
    return window.localStorage.getItem(GUIDE_SEEN_STORAGE_KEY) === "true";
  } catch {
    return true;
  }
}

function rememberGuideVisit(): void {
  try {
    window.localStorage.setItem(GUIDE_SEEN_STORAGE_KEY, "true");
  } catch {
    // Storage can be unavailable in privacy-restricted browsers.
  }
}

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
  const [firstVisitGuide, setFirstVisitGuide] = useState(false);
  const [resultOpen, setResultOpen] = useState(false);
  const [reverseNoticeVisible, setReverseNoticeVisible] = useState(false);
  const [infiniteSelectOpen, setInfiniteSelectOpen] = useState(false);
  const [startingPresetKey, setStartingPresetKey] = useState<string | null>(
    null,
  );
  const guideCheckComplete = useRef(false);
  const infiniteButtonRef = useRef<HTMLButtonElement>(null);
  const dailyContinuationToken = useRef<string | null>(null);

  const closeHelp = useCallback(() => {
    setHelpOpen(false);
    setFirstVisitGuide(false);
  }, []);
  const closeResult = useCallback(() => setResultOpen(false), []);
  const openHelp = useCallback(() => {
    if (!resultOpen) {
      setFirstVisitGuide(false);
      setHelpOpen(true);
    }
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

  useEffect(() => {
    if (!state.bootstrap || guideCheckComplete.current) return;
    guideCheckComplete.current = true;
    if (hasSeenGuide()) return;

    rememberGuideVisit();
    setFirstVisitGuide(true);
    setHelpOpen(true);
  }, [state.bootstrap]);

  const startGame = useCallback(async (mode: GameMode, presetKey?: string) => {
    setHelpOpen(false);
    setResultOpen(false);
    setStartingPresetKey(presetKey ?? null);
    dispatch({ type: "STARTING", mode });
    try {
      const continuationToken =
        mode === "daily" ? crypto.randomUUID() : undefined;
      if (mode === "daily") {
        dailyContinuationToken.current = continuationToken ?? null;
      }
      const session = await api.startGame(mode, presetKey, continuationToken);
      setInfiniteSelectOpen(false);
      dispatch({ type: "START_SUCCESS", payload: session });
    } catch (error) {
      dispatch({
        type: "FAILURE",
        scope: "start",
        message: errorMessage(error),
        recoverable: true,
      });
    } finally {
      setStartingPresetKey(null);
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

    const enteredGuess = state.currentGuess;
    dispatch({ type: "SUBMITTING" });
    const revealWindow = waitForRevealStart();
    try {
      const [result] = await Promise.all([
        api.submitGuess(
          state.session.gameId,
          state.currentGuess,
          state.session.mode === "daily"
            ? (dailyContinuationToken.current ?? undefined)
            : undefined,
        ),
        revealWindow,
      ]);
      dispatch({
        type: "GUESS_SUCCESS",
        payload: result,
        enteredGuess,
      });
    } catch (error) {
      dispatch({
        type: "FAILURE",
        scope: "guess",
        message: errorMessage(error),
        recoverable: isRecoverableServiceError(error),
      });
    }
  }, [state.currentGuess, state.phase, state.session]);

  const expireTimer = useCallback(async () => {
    if (!state.session || !state.timerActive) return;
    dispatch({ type: "TIMER_EXPIRING" });
    try {
      const result = await api.expireTimer(
        state.session.gameId,
        state.session.mode === "daily"
          ? (dailyContinuationToken.current ?? undefined)
          : undefined,
      );
      dispatch({ type: "TIMEOUT_SUCCESS", payload: result });
    } catch (error) {
      dispatch({
        type: "FAILURE",
        scope: "timer",
        message: errorMessage(error),
        recoverable: true,
      });
    }
  }, [state.session, state.timerActive]);

  useEffect(() => {
    if (state.phase !== "reversing") return;
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const timer = window.setTimeout(
      () => dispatch({ type: "REVERSE_COMPLETE" }),
      reducedMotion ? 120 : 320,
    );
    return () => window.clearTimeout(timer);
  }, [state.phase]);

  useEffect(() => {
    if (!state.reverseEntryActive) {
      setReverseNoticeVisible(false);
      return;
    }

    setReverseNoticeVisible(true);
    const timer = window.setTimeout(
      () => setReverseNoticeVisible(false),
      7_000,
    );
    return () => window.clearTimeout(timer);
  }, [state.reverseEntryActive]);

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
    if (state.phase !== "blackoutClosing") return;
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const timer = window.setTimeout(
      () => dispatch({ type: "BLACKOUT_COVERED" }),
      reducedMotion ? 80 : 160,
    );
    return () => window.clearTimeout(timer);
  }, [state.phase]);

  useEffect(() => {
    if (state.phase !== "blackoutOpening") return;
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const timer = window.setTimeout(
      () => dispatch({ type: "BLACKOUT_COMPLETE" }),
      reducedMotion ? 100 : 340,
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
    () => buildKeyboardFeedback(state.guesses, state.blackoutCutoffAttempt),
    [state.blackoutCutoffAttempt, state.guesses],
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
    const startError = state.phase === "error" ? state.message : undefined;
    if (infiniteSelectOpen) {
      return (
        <>
          <PracticeDifficultySelect
            presets={state.bootstrap.presets}
            busy={state.phase === "starting"}
            selectedPresetKey={startingPresetKey}
            message={startError}
            onBack={() => {
              setInfiniteSelectOpen(false);
              window.requestAnimationFrame(() =>
                infiniteButtonRef.current?.focus(),
              );
            }}
            onHelp={openHelp}
            onSelect={(presetKey) => void startGame("practice", presetKey)}
          />
          {helpOpen ? (
            <HowDeceptionWorks
              expandAll={firstVisitGuide}
              onClose={closeHelp}
            />
          ) : null}
        </>
      );
    }
    return (
      <>
        <ModeSelect
          daily={state.bootstrap.daily}
          busy={state.phase === "starting"}
          message={state.phase === "error" ? state.message : undefined}
          onStart={(mode) => void startGame(mode)}
          onInfinite={() => setInfiniteSelectOpen(true)}
          onHelp={openHelp}
          infiniteButtonRef={infiniteButtonRef}
        />
        {helpOpen ? (
          <HowDeceptionWorks expandAll={firstVisitGuide} onClose={closeHelp} />
        ) : null}
      </>
    );
  }

  if (!state.session) return null;

  const replayPresetKey = state.session.preset.presetKey;
  const latest = state.guesses.at(-1);
  const finished = state.phase === "won" || state.phase === "lost";
  const inputDisabled =
    state.phase === "submitting" ||
    state.phase === "expiring" ||
    state.phase === "reversing" ||
    state.phase === "revealing" ||
    state.phase === "blackoutClosing" ||
    state.phase === "blackoutOpening" ||
    state.phase === "intrusion" ||
    finished ||
    state.phase === "error";

  return (
    <main className="game-screen">
      <BrandHeader
        mode={state.session.mode}
        presetName={state.session.preset.name}
        helpDisabled={
          state.timerActive !== null ||
          state.phase === "blackoutClosing" ||
          state.phase === "blackoutOpening" ||
          state.phase === "intrusion"
        }
        timer={
          state.timerActive ? (
            <GuessTimer
              timer={state.timerActive}
              enabled={state.phase === "ready" || state.phase === "intrusion"}
              onExpire={() => void expireTimer()}
            />
          ) : undefined
        }
        onReturn={() => {
          setHelpOpen(false);
          setResultOpen(false);
          dailyContinuationToken.current = null;
          void loadBootstrap();
        }}
        onHelp={openHelp}
      />
      <div className="game-stage">
        <p className="visually-hidden" role="status" aria-live="polite">
          {state.announcement}
        </p>
        <div className="board-area">
          {reverseNoticeVisible ? (
            <div className="reverse-entry-strip" role="status">
              <strong>Type your next guess backwards</strong>
            </div>
          ) : null}
          <GameBoard
            wordLength={state.session.config.wordLength}
            maxGuesses={state.session.config.maxGuesses}
            currentGuess={state.currentGuess}
            guesses={state.guesses}
            revealing={state.phase === "revealing"}
            blackoutCutoffAttempt={state.blackoutCutoffAttempt}
            reverseTransition={
              state.reverseTransition
                ? {
                    enteredGuess: state.reverseTransition.enteredGuess,
                    decodedGuess: state.reverseTransition.result.guess,
                  }
                : null
            }
          />
          {state.intrusionActive ? (
            <Intrusion
              intrusion={state.intrusionActive}
              onDismiss={() => dispatch({ type: "DISMISS_INTRUSION" })}
            />
          ) : null}
        </div>

        <div className="game-status-line">
          {state.message ? (
            <p
              className={`game-status ${
                state.errorScope === "guess" || state.errorScope === "timer"
                  ? "game-status--error"
                  : ""
              }`}
              role={
                state.errorScope === "guess" || state.errorScope === "timer"
                  ? "alert"
                  : "status"
              }
              aria-live="polite"
            >
              {state.message}
            </p>
          ) : null}
          <p className="guess-progress">
            {state.guesses.length} of {state.session.config.maxGuesses} guesses
          </p>
        </div>

        {state.phase === "error" &&
        (state.errorScope === "guess" || state.errorScope === "timer") ? (
          <div className="inline-error-actions">
            <button
              className="text-button"
              type="button"
              onClick={() =>
                state.errorScope === "timer"
                  ? void expireTimer()
                  : void submitGuess()
              }
            >
              {state.errorScope === "timer" ? "Retry timer" : "Retry guess"}
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
            dailyStage={state.session.dailyStage}
            onClose={closeResult}
            onInfinite={() => {
              void startGame("practice", replayPresetKey);
            }}
            onDescend={() => void startGame("daily")}
            onModes={() => {
              setResultOpen(false);
              dailyContinuationToken.current = null;
              void loadBootstrap();
            }}
          />
        ) : null}
        {helpOpen && !resultOpen ? (
          <HowDeceptionWorks expandAll={firstVisitGuide} onClose={closeHelp} />
        ) : null}
      </div>
      {state.phase === "blackoutClosing" ||
      state.phase === "blackoutOpening" ? (
        <BlackoutCurtain
          stage={state.phase === "blackoutClosing" ? "closing" : "opening"}
        />
      ) : null}
    </main>
  );
}
