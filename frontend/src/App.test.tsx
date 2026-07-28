import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const bootstrap = {
  config: { wordLength: 5, maxGuesses: 6 },
  daily: {
    puzzleKey: "2026-07-28",
    availability: "available",
    resetAt: "2026-07-29T03:00:00Z",
  },
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

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
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(bootstrap))
      .mockResolvedValueOnce(
        jsonResponse({
          gameId: "practice-game",
          mode: "practice",
          config: bootstrap.config,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          guess: "crane",
          feedback: "GGGGG",
          attempt: 1,
          status: "won",
          answer: "crane",
        }),
      );

    render(<App />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Play Practice" }),
    );
    await screen.findByText("0 of 6 guesses");

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
        }),
      );

    render(<App />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Play Practice" }),
    );
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
    fireEvent.click(
      await screen.findByRole("button", { name: "Play Practice" }),
    );
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
});
