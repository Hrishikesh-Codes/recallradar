import { expect, test } from "@playwright/test";

/* The app is installable: a manifest with real icons, and a service worker in production. */
test("manifest describes an installable app with real icons", async ({ request }) => {
  const manifest = (await (await request.get("/manifest.webmanifest")).json()) as {
    display: string;
    start_url: string;
    icons: Array<{ src: string; sizes: string; purpose: string }>;
  };
  expect(manifest.display).toBe("standalone");
  expect(manifest.start_url).toBe("/check");
  expect(manifest.icons.some((icon) => icon.purpose === "maskable")).toBe(true);
  for (const icon of manifest.icons) {
    const response = await request.get(icon.src);
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toBe("image/png");
  }
});

test.describe("with the service worker", () => {
  test.use({ serviceWorkers: "allow" });

  test("it registers and the offline page exists", async ({ page }, testInfo) => {
    test.skip(
      testInfo.project.name === "iphone",
      "WebKit in Playwright doesn't run service workers",
    );
    await page.goto("/");
    const scope = await page.evaluate(async () => (await navigator.serviceWorker.ready).scope);
    expect(scope).toMatch(/\/$/);
    await page.goto("/offline");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/offline/i);
  });
});
