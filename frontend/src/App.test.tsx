import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App, { GUIDE_SEEN_STORAGE_KEY } from "./App";

const bootstrap = {
  config: { wordLength: 5, maxGuesses: 6 },
  daily: {
    puzzleKey: "2026-07-28",
    availability: "available",
    resetAt: "2026-07-29T03:00:00Z",
  },
  presets: [
    {
      presetKey: "doubt-1@1",
      name: "Doubt I",
      rank: 1,
      pressure: "Uneasy",
      description: "A measured first step into uncertainty.",
      available: true,
    },
    {
      presetKey: "doubt-2@1",
      name: "Doubt II",
      rank: 2,
      pressure: "Unsettling",
      description: "The familiar rules begin to push back.",
      available: true,
    },
    {
      presetKey: "doubt-3@1",
      name: "Doubt III",
      rank: 3,
      pressure: "Severe",
      description: "Relentless pressure rewards careful play.",
      available: true,
    },
    {
      presetKey: "deception@1",
      name: "Deception",
      rank: 4,
      pressure: "Merciless",
      description: "Nothing is offered without a cost.",
      available: true,
    },
  ],
};

async function startPractice(): Promise<void> {
  fireEvent.click(await screen.findByRole("button", { name: "Play Practice" }));
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Play Practice on Doubt II",
    }),
  );
}

const storage = new Map<string, string>();
const localStorageMock = {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
  clear: () => storage.clear(),
  key: (index: number) => Array.from(storage.keys()).at(index) ?? null,
  get length() {
    return storage.size;
  },
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  storage.clear();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: localStorageMock,
  });
  window.localStorage.setItem(GUIDE_SEEN_STORAGE_KEY, "true");
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("announces the loading state while bootstrap is pending", async () => {
    let resolveBootstrap: (response: Response) => void = () => {};
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveBootstrap = resolve;
      }),
    );
    render(<App />);

    expect(screen.getByRole("status")).toHaveTextContent("Connecting…");
    resolveBootstrap(jsonResponse(bootstrap));
    await screen.findByRole("button", { name: "Play Daily" });
  });

  it("renders the mode screen without serious accessibility violations", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(bootstrap));
    const { container } = render(<App />);

    await screen.findByRole("button", { name: "Play Daily" });
    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    const serious = results.violations.filter((violation) =>
      ["serious", "critical"].includes(violation.impact ?? ""),
    );

    expect(serious).toEqual([]);
  });

  it("completes the keyboard-driven practice win flow", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(bootstrap))
      .mockResolvedValueOnce(
        jsonResponse({
          gameId: "practice-game",
          mode: "practice",
          config: bootstrap.config,
          preset: bootstrap.presets[1],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          guess: "crane",
          feedback: "GGGGG",
          attempt: 1,
          status: "won",
          answer: "crane",
          deception: {
            events: [
              {
                outcome: "notActivated",
                scheduledAttempt: 4,
                reason: "notReached",
              },
            ],
          },
        }),
      );

    render(<App />);
    await startPractice();
    await screen.findByText("0 of 6 guesses");
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
      mode: "practice",
      presetKey: "doubt-2@1",
    });

    for (const letter of "crane") {
      fireEvent.keyDown(window, { key: letter });
    }
    fireEvent.keyDown(window, { key: "Enter" });

    expect(await screen.findByText("Revealing feedback…")).toBeInTheDocument();
    expect(
      await screen.findByRole(
        "heading",
        { name: "Word found." },
        { timeout: 2_000 },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("CRANE")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Play Again" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close result" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "View result" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "View result" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Row 4 was selected, but you finished before reaching it.",
      ),
    ).toBeInTheDocument();
  });

  it("opens the Deception Guide from the mode screen", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(bootstrap));
    render(<App />);

    const help = await screen.findByRole("button", {
      name: "Open Deception Guide",
    });
    help.focus();
    fireEvent.click(help);

    expect(
      screen.getByRole("heading", { name: "Deception Guide" }),
    ).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(help).toHaveFocus();
  });

  it("opens the complete guide automatically on a first visit", async () => {
    window.localStorage.removeItem(GUIDE_SEEN_STORAGE_KEY);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(bootstrap));

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Deception Guide" }),
    ).toBeInTheDocument();
    const disclosures = screen
      .getAllByText(/How it works|Possible punishments/)
      .map((label) => label.closest("details"));
    expect(disclosures).toHaveLength(2);
    expect(disclosures.every((details) => details?.hasAttribute("open"))).toBe(
      true,
    );
    expect(window.localStorage.getItem(GUIDE_SEEN_STORAGE_KEY)).toBe("true");
  });

  it("keeps a short guess local and does not call the guess API", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(bootstrap))
      .mockResolvedValueOnce(
        jsonResponse({
          gameId: "practice-game",
          mode: "practice",
          config: bootstrap.config,
          preset: bootstrap.presets[1],
        }),
      );

    render(<App />);
    await startPractice();
    await screen.findByText("0 of 6 guesses");

    for (const letter of "cat") {
      fireEvent.keyDown(window, { key: letter });
    }
    fireEvent.keyDown(window, { key: "Enter" });

    expect(
      await screen.findByText("Enter exactly 5 letters."),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers retry when bootstrap cannot reach the API", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Game service unavailable",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Retry connection" }),
    ).toBeEnabled();
  });

  it("keeps an invalid dictionary guess editable", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(bootstrap))
      .mockResolvedValueOnce(
        jsonResponse({
          gameId: "practice-game",
          mode: "practice",
          config: bootstrap.config,
          preset: bootstrap.presets[1],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "INVALID_WORD",
              message: "That word is not in the accepted word list.",
            },
          },
          400,
        ),
      );

    render(<App />);
    await startPractice();
    await screen.findByText("0 of 6 guesses");
    for (const letter of "zzzzz") {
      fireEvent.keyDown(window, { key: letter });
    }
    fireEvent.keyDown(window, { key: "Enter" });

    expect(
      await screen.findByText("That word is not in the accepted word list."),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("cell", { name: "Z, not submitted" }),
    ).toHaveLength(5);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Enter" })).toBeEnabled(),
    );
  });

  it("shows an activated Guess Timer after feedback finishes", async () => {
    const startsAt = new Date(Date.now() + 1_000);
    const deadlineAt = new Date(startsAt.getTime() + 30_000);
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(bootstrap))
      .mockResolvedValueOnce(
        jsonResponse({
          gameId: "practice-game",
          mode: "practice",
          config: bootstrap.config,
          preset: bootstrap.presets[1],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          guess: "slate",
          feedback: "BBGBG",
          attempt: 1,
          status: "playing",
          timer: {
            state: "activated",
            durationSeconds: 30,
            startsAt: startsAt.toISOString(),
            deadlineAt: deadlineAt.toISOString(),
          },
        }),
      );

    render(<App />);
    await startPractice();
    await screen.findByText("0 of 6 guesses");
    for (const letter of "slate") {
      fireEvent.keyDown(window, { key: letter });
    }
    fireEvent.keyDown(window, { key: "Enter" });

    expect(
      await screen.findByText("0:30", undefined, { timeout: 2_000 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Open Deception Guide" }),
    ).toBeDisabled();
  });

  it("activates Reverse Entry and submits the next word backwards", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(bootstrap))
      .mockResolvedValueOnce(
        jsonResponse({
          gameId: "practice-game",
          mode: "practice",
          config: bootstrap.config,
          preset: bootstrap.presets[1],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          guess: "fight",
          feedback: "BBBBB",
          attempt: 1,
          status: "playing",
          reverseEntry: { state: "activated" },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          guess: "crane",
          feedback: "GGGGG",
          attempt: 2,
          status: "won",
          answer: "crane",
          reverseEntry: { state: "resolved" },
        }),
      );

    render(<App />);
    await startPractice();
    await screen.findByText("0 of 6 guesses");

    for (const letter of "fight") {
      fireEvent.keyDown(window, { key: letter });
    }
    fireEvent.keyDown(window, { key: "Enter" });

    expect(
      await screen.findByText("Type your next guess backwards", undefined, {
        timeout: 2_000,
      }),
    ).toBeInTheDocument();
    for (const letter of "enarc") {
      fireEvent.keyDown(window, { key: letter });
    }
    fireEvent.keyDown(window, { key: "Enter" });

    await screen.findByText(
      "Reverse entry accepted as CRANE. Revealing feedback.",
    );
    const submitted = JSON.parse(
      String(fetchMock.mock.calls[3]?.[1]?.body),
    ) as { guess: string };
    expect(submitted.guess).toBe("enarc");
    expect(
      await screen.findByRole(
        "heading",
        { name: "Word found." },
        { timeout: 2_000 },
      ),
    ).toBeInTheDocument();
  });

  it("keeps Reverse Entry active after an invalid backwards word", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(bootstrap))
      .mockResolvedValueOnce(
        jsonResponse({
          gameId: "practice-game",
          mode: "practice",
          config: bootstrap.config,
          preset: bootstrap.presets[1],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          guess: "fight",
          feedback: "BBBBB",
          attempt: 1,
          status: "playing",
          reverseEntry: { state: "activated" },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "INVALID_REVERSED_WORD",
              message: "That guess isn’t accepted.",
            },
          },
          400,
        ),
      );

    render(<App />);
    await startPractice();
    await screen.findByText("0 of 6 guesses");
    for (const letter of "fight") {
      fireEvent.keyDown(window, { key: letter });
    }
    fireEvent.keyDown(window, { key: "Enter" });
    await screen.findByText("Type your next guess backwards", undefined, {
      timeout: 2_000,
    });

    for (const letter of "zzzzz") {
      fireEvent.keyDown(window, { key: letter });
    }
    fireEvent.keyDown(window, { key: "Enter" });

    expect(
      await screen.findByText("That guess isn’t accepted."),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("cell", { name: "Z, not submitted" }),
    ).toHaveLength(5);
  });
});
