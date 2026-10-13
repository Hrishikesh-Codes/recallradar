import { expect, test } from "@playwright/test";

test.describe("reduced motion", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "reduced-motion", "reduced-motion project only");
  });

  test("hero lines are static and smooth scrolling is off", async ({ page }) => {
    await page.goto("/");
    const firstLine = page.locator("h1 .reveal-line__inner").first();
    await expect(firstLine).toBeVisible();
    // No slide-up: the line is already in place on first paint.
    expect(await firstLine.evaluate((el) => getComputedStyle(el).transform)).toBe("none");
    // Lenis adds a "lenis" class to <html> when it runs.
    await expect(page.locator("html")).not.toHaveClass(/lenis/);
  });

  test("scroll reveals never hide content", async ({ page }) => {
    await page.goto("/");
    const statement = page.getByRole("heading", { name: /we checked/i });
    await statement.scrollIntoViewIfNeeded();
    await expect(statement).toBeVisible();
    await expect(statement).not.toHaveAttribute("data-reveal", "armed");
  });
});

test.describe("full motion", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "desktop project only");
  });

  test("smooth scrolling runs on marketing pages", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("html")).toHaveClass(/lenis/);
  });

  test("offscreen statements reveal when scrolled into view", async ({ page }) => {
    await page.goto("/");
    const statement = page.getByRole("heading", { name: /we checked/i });
    await expect(statement).toHaveAttribute("data-reveal", "armed");
    await statement.scrollIntoViewIfNeeded();
    await expect(statement).not.toHaveAttribute("data-reveal", "armed");
  });
});
