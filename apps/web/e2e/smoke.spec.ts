import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const PAGES = ["/", "/dev"] as const;

async function seriousA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  return results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`);
}

for (const path of PAGES) {
  test(`${path} renders without horizontal scroll or serious a11y violations`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBe(0);
    expect(await seriousA11yViolations(page)).toEqual([]);
  });
}

test("home headline says what the product does", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    /Know if what\s*you own was\s*recalled/i,
  );
  await expect(page).toHaveTitle("RecallRadar");
});

test("menu opens, is keyboard reachable, and closes with Escape", async ({ page }) => {
  await page.goto("/");
  const toggle = page.getByRole("button", { name: "Open menu" });
  await toggle.click();
  const menu = page.getByRole("navigation", { name: "Main" });
  await expect(menu.getByRole("link", { name: "Design system" })).toBeVisible();
  await expect(menu.getByRole("link").first()).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  await expect(page.getByRole("button", { name: "Open menu" })).toBeFocused();
});

test("menu navigates to the design system", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Open menu" }).click();
  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "Design system" })
    .click();
  await expect(page).toHaveURL(/\/dev$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Tokens and components/i);
});

test("skip link jumps to the main content", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "mobile", "keyboard-only flow");
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await skip.press("Enter");
  await expect(page).toHaveURL(/#main$/);
});

test("every verdict state is labelled in words", async ({ page }) => {
  await page.goto("/dev");
  for (const label of [
    "Recalled",
    "Check your unit",
    "All clear",
    "Couldn't identify",
    "Can't check yet",
  ]) {
    await expect(page.getByRole("heading", { level: 3, name: label })).toBeVisible();
  }
});
