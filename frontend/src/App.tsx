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
const TIMER_EXPIRY_RETRY_DELAY_MS = 100;

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

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
  const sessionEpoch = useRef(0);
  const attemptRequest = useRef(0);

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
    const epoch = sessionEpoch.current + 1;
    sessionEpoch.current = epoch;
    attemptRequest.current += 1;
    dispatch({ type: "BOOTSTRAP_LOADING" });
    try {
      const bootstrap = await api.bootstrap();
      if (sessionEpoch.current !== epoch) return;
      dispatch({ type: "BOOTSTRAP_SUCCESS", payload: bootstrap });
    } catch (error) {
      if (sessionEpoch.current !== epoch) return;
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
    const epoch = sessionEpoch.current;
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
      if (sessionEpoch.current !== epoch) return;
      setInfiniteSelectOpen(false);
      dispatch({ type: "START_SUCCESS", payload: session });
    } catch (error) {
      if (sessionEpoch.current !== epoch) return;
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
    const retryingGuess =
      state.phase === "error" && state.errorScope === "guess";
    if (!state.session || (state.phase !== "ready" && !retryingGuess)) return;
    if (state.currentGuess.length !== state.session.config.wordLength) {
      dispatch({
        type: "LOCAL_MESSAGE",
        message: `Enter exactly ${state.session.config.wordLength} letters.`,
      });
      return;
    }

    const enteredGuess = state.currentGuess;
    const gameId = state.session.gameId;
    const epoch = sessionEpoch.current;
    const request = attemptRequest.current + 1;
    attemptRequest.current = request;
    dispatch({ type: "SUBMITTING" });
    const revealWindow = waitForRevealStart();
    try {
      const [result] = await Promise.all([
        api.submitGuess(
          gameId,
          state.currentGuess,
          state.session.mode === "daily"
            ? (dailyContinuationToken.current ?? undefined)
            : undefined,
        ),
        revealWindow,
      ]);
      if (
        sessionEpoch.current !== epoch ||
        attemptRequest.current !== request
      ) {
        return;
      }
      dispatch({
        type: "GUESS_SUCCESS",
        payload: result,
        enteredGuess,
      });
    } catch (error) {
      if (
        sessionEpoch.current !== epoch ||
        attemptRequest.current !== request
      ) {
        return;
      }
      dispatch({
        type: "FAILURE",
        scope: "guess",
        message: errorMessage(error),
        recoverable: isRecoverableServiceError(error),
        code: error instanceof ApiError ? error.code : undefined,
      });
    }
  }, [state.currentGuess, state.errorScope, state.phase, state.session]);

  useEffect(() => {
    if (
      state.phase === "ready" &&
      state.activeInputPunishment === "forcedCommitment" &&
      state.session &&
      state.currentGuess.length === state.session.config.wordLength
    ) {
      void submitGuess();
    }
  }, [
    state.activeInputPunishment,
    state.currentGuess.length,
    state.phase,
    state.session,
    submitGuess,
  ]);

  const expireTimer = useCallback(async () => {
    if (!state.session || !state.timerActive) return;
    const gameId = state.session.gameId;
    const epoch = sessionEpoch.current;
    const request = attemptRequest.current + 1;
    attemptRequest.current = request;
    dispatch({ type: "TIMER_EXPIRING" });
    for (;;) {
      if (
        sessionEpoch.current !== epoch ||
        attemptRequest.current !== request
      ) {
        return;
      }
      try {
        const result = await api.expireTimer(
          gameId,
          state.session.mode === "daily"
            ? (dailyContinuationToken.current ?? undefined)
            : undefined,
        );
        if (
          sessionEpoch.current !== epoch ||
          attemptRequest.current !== request
        ) {
          return;
        }
        dispatch({ type: "TIMEOUT_SUCCESS", payload: result });
        return;
      } catch (error) {
        if (error instanceof ApiError && error.code === "TIMER_STILL_RUNNING") {
          await wait(TIMER_EXPIRY_RETRY_DELAY_MS);
          continue;
        }
        if (
          sessionEpoch.current !== epoch ||
          attemptRequest.current !== request
        ) {
          return;
        }
        dispatch({
          type: "FAILURE",
          scope: "timer",
          message: errorMessage(error),
          recoverable: true,
        });
        return;
      }
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

  const activePunishmentLabels = [
    reverseNoticeVisible && state.reverseEntryActive ? "Reverse Entry" : null,
    state.activeInputPunishment === "blindEntry"
      ? "Blind Entry"
      : state.activeInputPunishment === "forcedCommitment"
        ? "Forced Commitment"
        : state.activeInputPunishment === "noRevision"
          ? "No Revision"
          : null,
    state.memoryTaxActive ? "Memory Tax" : null,
    state.corruptedRowAttempt !== null ? "History Corrupted" : null,
  ].filter((label): label is string => label !== null);

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
          {activePunishmentLabels.length ? (
            <div className="punishment-status" role="status">
              <ul aria-label="Active punishments">
                {activePunishmentLabels.map((label) => (
                  <li key={label}>{label}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <GameBoard
            wordLength={state.session.config.wordLength}
            maxGuesses={state.session.config.maxGuesses}
            currentGuess={state.currentGuess}
            guesses={state.guesses}
            revealing={state.phase === "revealing"}
            blackoutCutoffAttempt={state.blackoutCutoffAttempt}
            corruptedRowAttempt={state.corruptedRowAttempt}
            memoryTaxRetainRows={
              state.memoryTaxActive ? state.memoryTaxRetainRows : null
            }
            blindCurrentEntry={state.activeInputPunishment === "blindEntry"}
            forcedCommitmentActive={
              state.activeInputPunishment === "forcedCommitment"
            }
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
          backspaceLocked={
            state.activeInputPunishment === "noRevision" &&
            state.currentGuess.length > 0
          }
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
