import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("practice can be solved with the physical keyboard", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Play Practice" }).click();
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  await page.keyboard.type("crane");
  await page.keyboard.press("Enter");

  await expect(
    page.getByRole("heading", { name: "Word found." }),
  ).toBeVisible();
  await expect(page.getByRole("dialog").getByText("CRANE")).toBeVisible();
  await expect(
    page.getByText(
      "The lie was waiting on row 1. Solving the word kept that row truthful.",
    ),
  ).toBeVisible();

  const accessibility = await new AxeBuilder({ page }).analyze();
  const serious = accessibility.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(serious).toEqual([]);
});

test("an activated lie is audited after the game", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Play Practice" }).click();

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
      /Row 1 lied\. T was shown as in the word in another position\./,
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close result" }).click();
  await expect(page.getByRole("button", { name: "View result" })).toBeVisible();
  await page.getByRole("button", { name: "View result" }).click();
  await expect(
    page.getByRole("heading", { name: "What happened" }),
  ).toBeVisible();
});

test("How Deception Works is keyboard accessible", async ({ page }) => {
  await page.goto("/");
  const trigger = page.getByRole("button", {
    name: "How Deception Works",
  });
  await trigger.focus();
  await trigger.press("Enter");

  await expect(
    page.getByRole("heading", { name: "How Deception Works" }),
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
  await page.getByRole("button", { name: "Play Practice" }).click();
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  for (const letter of "CRANE") {
    await page.getByRole("button", { name: letter, exact: true }).click();
  }
  await page.getByRole("button", { name: "Enter", exact: true }).click();

  await expect(
    page.getByRole("heading", { name: "Word found." }),
  ).toBeVisible();
});

test("invalid Daily guess does not consume, valid guess does", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Play Daily" }).click();
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  await page.keyboard.type("zzzzz");
  await page.keyboard.press("Enter");
  await expect(
    page.getByText("That word is not in the accepted word list."),
  ).toBeVisible();

  await page.getByRole("button", { name: "Return to modes" }).click();
  await expect(page.getByRole("button", { name: "Play Daily" })).toBeEnabled();
  await page.getByRole("button", { name: "Play Daily" }).click();
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  for (let index = 0; index < 5; index += 1) {
    await page.keyboard.press("Backspace");
  }
  await page.keyboard.type("slate");
  await page.keyboard.press("Enter");
  await expect(page.getByText("1 of 6 guesses")).toBeVisible();

  await page.reload();
  await expect(page.getByRole("button", { name: "Daily Used" })).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Play Practice" }),
  ).toBeEnabled();
});

test("practice loss reveals the answer after six guesses", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Play Practice" }).click();
  await expect(page.getByText("0 of 6 guesses")).toBeVisible();

  for (const [index, guess] of [
    "slate",
    "fight",
    "mould",
    "berry",
    "shack",
    "dingo",
  ].entries()) {
    await page.keyboard.type(guess);
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
  await page.getByRole("button", { name: "Play Practice" }).click();

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
    page.getByRole("button", { name: "How Deception Works" }),
  ).toBeVisible();

  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "How Deception Works" }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Play Daily" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Play Practice" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
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
