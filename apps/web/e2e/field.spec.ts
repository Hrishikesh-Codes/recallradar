import { expect, test } from "@playwright/test";

/*
 * Text over the landing page's WebGL field keeps WCAG contrast: the brightest canvas pixel
 * behind each [data-field-shade] block, over several animation frames, against every text
 * colour in it. Display type (data-field-shade="large") needs 3:1, everything else 4.5:1. Text
 * on its own solid background (buttons, fields) is measured by axe instead.
 */

type Sample = { text: string; large: boolean; ratio: number };

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "needs WebGL (software in the desktop project)");
});

test("hero text keeps its contrast over the field", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-field-on", "");
  const samples: Sample[] = [];
  for (let frame = 0; frame < 4; frame++) {
    await page.waitForTimeout(600);
    samples.push(...(await page.evaluate(measure)));
  }
  expect(samples.length).toBeGreaterThan(3);
  for (const sample of samples) {
    expect(sample.ratio, sample.text).toBeGreaterThanOrEqual(sample.large ? 3 : 4.5);
  }
});

// Notes and how-it-works steps sit on the dots with no box: the dots dim behind them.
for (const text of ["Barcodes, model numbers", "We keep watching"]) {
  test(`"${text}" keeps its contrast over the dots`, async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-field-on", "");
    const block = page.locator("[data-field-shade]").filter({ hasText: text });
    await block.scrollIntoViewIfNeeded();
    await page.waitForTimeout(1200);
    const samples: Sample[] = [];
    for (let frame = 0; frame < 3; frame++) {
      await page.waitForTimeout(400);
      samples.push(...(await page.evaluate(measure)));
    }
    expect(samples.some((sample) => sample.text.includes(text.split(",")[0]!))).toBe(true);
    for (const sample of samples) {
      expect(sample.ratio, sample.text).toBeGreaterThanOrEqual(sample.large ? 3 : 4.5);
    }
  });
}

function measure(): Promise<Sample[]> {
  return new Promise((resolve) =>
    // Two frames in: the field has drawn, and its buffer is still readable.
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        const canvas = document.querySelector("canvas")!;
        const gl = canvas.getContext("webgl2")!;
        const sx = canvas.width / innerWidth;
        const sy = canvas.height / innerHeight;
        const luminance = ([r, g, b]: number[]) => {
          const f = (v: number) => {
            v /= 255;
            return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
          };
          return 0.2126 * f(r!) + 0.7152 * f(g!) + 0.0722 * f(b!);
        };
        const rgb = (css: string) => (css.match(/\d+(\.\d+)?/g) ?? []).slice(0, 3).map(Number);
        // Labels on their own solid fill (primary buttons, fields) aren't over the field.
        const ownBackground = (n: Element) => n.closest(".btn--primary, input, textarea") !== null;
        const out: Sample[] = [];
        // One read of the whole frame (single-pixel reads each stall the GPU).
        const frame = new Uint8Array(canvas.width * canvas.height * 4);
        gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, frame);
        for (const block of document.querySelectorAll<HTMLElement>("[data-field-shade]")) {
          const r = block.getBoundingClientRect();
          if (r.bottom < 0 || r.top > innerHeight || r.width === 0) continue;
          let brightest = 0;
          for (let y = Math.max(0, r.top); y < Math.min(innerHeight, r.bottom); y += 6) {
            for (let x = Math.max(0, r.left); x < Math.min(innerWidth, r.right); x += 6) {
              const px = Math.floor(x * sx);
              const py = Math.floor(canvas.height - 1 - y * sy);
              const i = (py * canvas.width + px) * 4;
              brightest = Math.max(brightest, luminance([frame[i]!, frame[i + 1]!, frame[i + 2]!]));
            }
          }
          const texts = [block, ...block.querySelectorAll("*")].filter(
            (n) =>
              [...n.childNodes].some(
                (t) => t.nodeType === Node.TEXT_NODE && t.textContent?.trim(),
              ) && !ownBackground(n),
          );
          for (const n of texts) {
            const fg = luminance(rgb(getComputedStyle(n).color));
            const ratio = (Math.max(fg, brightest) + 0.05) / (Math.min(fg, brightest) + 0.05);
            out.push({
              text: (n.textContent ?? "").trim().slice(0, 40),
              large: block.dataset.fieldShade === "large",
              ratio,
            });
          }
        }
        resolve(out);
      }),
    ),
  );
}
