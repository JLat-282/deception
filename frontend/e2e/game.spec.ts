import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const presets = [
  {
    presetKey: "doubt-1@1",
    name: "Doubt I",
    rank: 1,
    pressure: "Low",
    description: "An approachable introduction to uncertain feedback.",
    available: true,
  },
  {
    presetKey: "doubt-2@1",
    name: "Doubt II",
    rank: 2,
    pressure: "Standard",
    description: "The complete standard Deception experience.",
    available: true,
  },
  {
    presetKey: "doubt-3@1",
    name: "Doubt III",
    rank: 3,
    pressure: "High",
    description: "Aggressive pressure with repeated punishments.",
    available: true,
  },
  {
    presetKey: "deception@1",
    name: "Deception",
    rank: 4,
    pressure: "Extreme",
    description: "An expert survival challenge.",
    available: true,
  },
];

async function startPractice(page: Page, preset = "Doubt II") {
  await page.getByRole("button", { name: "Play Infinite" }).click();
  await page
    .getByRole("button", {
      name: `Play Infinite on ${preset}`,
      exact: true,
    })
    .click();
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("deception-guide-seen-v1", "true");
  });
});

test("Daily Descent and Infinite form the primary mode choice", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Daily Descent" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Infinite" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Begin Descent" }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "Play Infinite" }),
  ).toBeEnabled();
  await expect(page.getByText("Doubt I", { exact: true })).toBeVisible();
  await expect(page.getByText("Deception", { exact: true })).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);

  const accessibility = await new AxeBuilder({ page }).analyze();
  const serious = accessibility.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(serious).toEqual([]);

  if (process.env.DECEPTION_CAPTURE_HOME === "true") {
    await page.screenshot({
      path: `../.qa/daily-descent-${testInfo.project.name}.png`,
      fullPage: true,
    });
  }
});

test("practice can be solved with the physical keyboard", async ({ page }) => {
  await page.goto("/");
  await startPractice(page);
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  await page.keyboard.type("crane");
  await page.keyboard.press("Enter");

  await expect(
    page.getByRole("heading", { name: "Word found." }),
  ).toBeVisible();
  await expect(page.getByRole("dialog").getByText("CRANE")).toBeVisible();
  await expect(
    page.getByText(
      "Row 1 was selected, but a winning guess always stays truthful.",
    ),
  ).toBeVisible();
  await expect(
    page.getByText("Row 2 was selected, but you finished before reaching it."),
  ).toBeVisible();

  const accessibility = await new AxeBuilder({ page }).analyze();
  const serious = accessibility.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(serious).toEqual([]);
});

test("Deception can be selected for Infinite", async ({ page }) => {
  await page.goto("/");
  await startPractice(page, "Deception");

  await expect(page.getByText("Infinite · Deception")).toBeVisible();
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();
});

test("an activated lie is audited after the game", async ({ page }) => {
  await page.goto("/");
  await startPractice(page);

  await page.getByRole("table").click();
  await page.keyboard.type("slate", { delay: 25 });
  await page.keyboard.press("Enter");
  await expect(page.getByText("1 of 6 guesses")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Enter", exact: true }),
  ).toBeEnabled();
  await page.keyboard.type("crane");
  await page.keyboard.press("Enter");

  await expect(
    page.getByText(
      /Row 1 lied on one tile\. E was shown as in the word in another position/,
    ),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Row 2 was selected, but a winning guess always stays truthful.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close result" }).click();
  await expect(page.getByRole("button", { name: "View result" })).toBeVisible();
  await page.getByRole("button", { name: "View result" }).click();
  await expect(
    page.getByRole("heading", { name: "What happened" }),
  ).toBeVisible();
});

test("the Deception Guide is keyboard accessible", async ({ page }) => {
  await page.goto("/");
  const trigger = page.getByRole("button", {
    name: "Open Deception Guide",
  });
  await trigger.focus();
  await trigger.press("Enter");

  await expect(
    page.getByRole("heading", { name: "Deception Guide" }),
  ).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  const serious = accessibility.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(serious).toEqual([]);

  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
});

test("practice can be solved with the on-screen keyboard", async ({ page }) => {
  await page.goto("/");
  await startPractice(page);
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  for (const letter of "CRANE") {
    await page.getByRole("button", { name: letter, exact: true }).click();
  }
  await page.getByRole("button", { name: "Enter", exact: true }).click();

  await expect(
    page.getByRole("heading", { name: "Word found." }),
  ).toBeVisible();
});

test("Reverse Entry decodes and reveals the next accepted guess", async ({
  page,
}) => {
  await page.goto("/");
  await startPractice(page);
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  await page.keyboard.type("fight");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Type your next guess backwards")).toBeVisible();

  await page.keyboard.type("enarc");
  await page.keyboard.press("Enter");

  await expect(
    page.getByRole("status").filter({
      hasText: "Reverse entry accepted as CRANE",
    }),
  ).toBeAttached();
  await expect(
    page.getByRole("heading", { name: "Word found." }),
  ).toBeVisible();
  await expect(page.getByRole("dialog").getByText("CRANE")).toBeVisible();
});

test("invalid Daily guess does not consume, valid guess does", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Begin Descent" }).click();
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  await page.keyboard.type("zzzzz");
  await page.keyboard.press("Enter");
  await expect(
    page.getByText("That word is not in the accepted word list."),
  ).toBeVisible();

  await page.getByRole("button", { name: "Return to modes" }).click();
  await expect(
    page.getByRole("button", { name: "Begin Descent" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Begin Descent" }).click();
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  for (let index = 0; index < 5; index += 1) {
    await page.keyboard.press("Backspace");
  }
  await page.keyboard.type("slate");
  await page.keyboard.press("Enter");
  await expect(page.getByText("1 of 6 guesses")).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole("button", { name: "Descent Ended" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Play Infinite" }),
  ).toBeEnabled();
});

test("practice loss reveals the answer after six guesses", async ({ page }) => {
  await page.goto("/");
  await startPractice(page);
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  for (const [index, entry] of [
    "slate",
    "fight",
    "dluom",
    "berry",
    "shack",
    "dingo",
  ].entries()) {
    await page.keyboard.type(entry);
    await page.keyboard.press("Enter");
    if (index < 5) {
      await expect(page.getByText(`${index + 1} of 6 guesses`)).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Enter", exact: true }),
      ).toBeEnabled();
    }
  }

  await expect(
    page.getByRole("heading", { name: "The word escaped." }),
  ).toBeVisible();
  await expect(page.getByText("CRANE")).toBeVisible();
});

test("primary surface fits the current viewport", async ({ page }) => {
  await page.goto("/");
  await startPractice(page);

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByLabel("On-screen keyboard")).toBeVisible();

  const accessibility = await new AxeBuilder({ page }).analyze();
  const serious = accessibility.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(serious).toEqual([]);
});

test("focus order and reduced-motion reveal remain usable", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Open Deception Guide" }),
  ).toBeVisible();

  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Open Deception Guide" }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Begin Descent" }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Play Infinite" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await page
    .getByRole("button", {
      name: "Play Infinite on Doubt II",
      exact: true,
    })
    .click();
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  const reducedAnimation = await page
    .locator(".tile")
    .first()
    .evaluate((element) => {
      element.classList.add("tile--revealing");
      const animationName = getComputedStyle(element).animationName;
      element.classList.remove("tile--revealing");
      return animationName;
    });
  expect(reducedAnimation).toBe("tile-fade");

  await page.keyboard.type("crane");
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Word found." }),
  ).toBeVisible();
});

test("Blackout closes after row reveal and erases accumulated feedback", async ({
  page,
}) => {
  let attempt = 0;
  await page.route("**/api/bootstrap", (route) =>
    route.fulfill({
      json: {
        config: { wordLength: 5, maxGuesses: 6 },
        daily: {
          puzzleKey: "2026-07-28",
          availability: "available",
          resetAt: "2026-07-29T03:00:00Z",
          status: "unstarted",
          currentStage: 1,
          clearedStages: 0,
        },
        presets,
      },
    }),
  );
  await page.route("**/api/games", (route) =>
    route.fulfill({
      json: {
        gameId: "blackout-game",
        mode: "practice",
        config: { wordLength: 5, maxGuesses: 6 },
        preset: presets[1],
      },
    }),
  );
  await page.route("**/api/games/blackout-game/guesses", (route) => {
    attempt += 1;
    const guesses = ["slate", "fight", "picky"];
    route.fulfill({
      json: {
        guess: guesses[attempt - 1],
        feedback: attempt === 1 ? "BBGBG" : "BBBBB",
        attempt,
        status: "playing",
        ...(attempt === 3 ? { blackout: { state: "activated" } } : {}),
      },
    });
  });

  await page.goto("/");
  await startPractice(page);
  for (const [index, guess] of ["slate", "fight", "picky"].entries()) {
    await page.keyboard.type(guess);
    await page.keyboard.press("Enter");
    if (index < 2) {
      await expect(page.getByText(`${index + 1} of 6 guesses`)).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Enter", exact: true }),
      ).toBeEnabled();
    }
  }

  await expect(page.locator(".blackout-curtain")).toBeVisible();
  if (process.env.DECEPTION_CAPTURE_BLACKOUT === "true") {
    await page.screenshot({
      path: "../output/playwright/blackout-curtain.png",
      fullPage: true,
    });
  }
  await expect(page.locator(".tile--blackout")).toHaveCount(15);
  await expect(page.locator(".blackout-curtain")).toBeHidden();
  await expect(page.getByRole("button", { name: "Enter" })).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "A", exact: true }),
  ).not.toHaveClass(/key--[gyb]/);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  if (process.env.DECEPTION_CAPTURE_BLACKOUT === "true") {
    await page.screenshot({
      path: "../output/playwright/blackout-result.png",
      fullPage: true,
    });
  }
});

test("Intrusion blocks play without pausing an active Timer", async ({
  page,
}) => {
  let attempt = 0;
  await page.route("**/api/bootstrap", (route) =>
    route.fulfill({
      json: {
        config: { wordLength: 5, maxGuesses: 6 },
        daily: {
          puzzleKey: "2026-07-28",
          availability: "available",
          resetAt: "2026-07-29T03:00:00Z",
          status: "unstarted",
          currentStage: 1,
          clearedStages: 0,
        },
        presets,
      },
    }),
  );
  await page.route("**/api/games", (route) =>
    route.fulfill({
      json: {
        gameId: "intrusion-game",
        mode: "practice",
        config: { wordLength: 5, maxGuesses: 6 },
        preset: presets[2],
      },
    }),
  );
  await page.route("**/api/games/intrusion-game/guesses", (route) => {
    attempt += 1;
    const now = Date.now();
    route.fulfill({
      json: {
        guess: attempt === 1 ? "slate" : "fight",
        feedback: "BBBBB",
        attempt,
        status: "playing",
        ...(attempt === 2
          ? {
              intrusion: { state: "activated", placement: "lowerRight" },
              timer: {
                state: "activated",
                durationSeconds: 30,
                startsAt: new Date(now).toISOString(),
                deadlineAt: new Date(now + 30_000).toISOString(),
              },
            }
          : {}),
      },
    });
  });

  await page.goto("/");
  await startPractice(page, "Doubt III");
  for (const [index, guess] of ["slate", "fight"].entries()) {
    await page.keyboard.type(guess);
    await page.keyboard.press("Enter");
    await expect(page.getByText(`${index + 1} of 6 guesses`)).toBeVisible();
    if (index === 0) {
      await expect(
        page.getByRole("button", { name: "Enter", exact: true }),
      ).toBeEnabled();
    }
  }

  const intrusion = page.getByRole("dialog", { name: "Intrusion" });
  await expect(intrusion).toBeVisible();
  const shield = page.locator(".intrusion-shield");
  const shieldBounds = await shield.boundingBox();
  const viewport = page.viewportSize();
  expect(shieldBounds?.width).toBe(viewport?.width);
  expect(shieldBounds?.height).toBe(viewport?.height);
  if (process.env.DECEPTION_CAPTURE_INTRUSION === "true") {
    await page.screenshot({
      path: "../output/playwright/intrusion.png",
      fullPage: true,
    });
  }
  const dismiss = page.getByRole("button", { name: "Dismiss" });
  await expect(dismiss).toBeFocused();
  const dismissBefore = await dismiss.boundingBox();
  const aKey = page.locator(".keyboard button").filter({ hasText: /^A$/ });
  await expect(aKey).toBeDisabled();
  const timer = page.locator(".guess-timer");
  const before = await timer.getAttribute("aria-label");
  await page.waitForTimeout(1_100);
  const after = await timer.getAttribute("aria-label");
  const dismissAfter = await dismiss.boundingBox();
  expect(after).not.toBe(before);
  expect(dismissAfter).not.toEqual(dismissBefore);
  await page.keyboard.press("Escape");
  await page.keyboard.press("Enter");
  await expect(intrusion).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  const serious = accessibility.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(serious).toEqual([]);

  await dismiss.evaluate((button: HTMLButtonElement) => button.click());
  await expect(intrusion).toBeHidden();
  await expect(aKey).toBeEnabled();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});
