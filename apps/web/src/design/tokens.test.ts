import { readFileSync } from "node:fs";
import { join } from "node:path";

import { composite, contrastRatio, hexToRgb } from "@/design/contrast";
import { colors, contrastRules, surfaces, type ContrastRule } from "@/design/tokens";

const css = readFileSync(join(__dirname, "../app/globals.css"), "utf8");

function background(bg: ContrastRule["bg"]) {
  if (bg in surfaces) {
    const [token, alpha] = surfaces[bg as keyof typeof surfaces];
    return composite(hexToRgb(colors[token]), alpha, hexToRgb(colors["bg-0"]));
  }
  return hexToRgb(colors[bg as keyof typeof colors]);
}

describe("globals.css mirrors tokens.ts", () => {
  it.each(Object.entries(colors))("--color-%s is %s", (name, hex) => {
    const declared = new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6});`, "i").exec(css)?.[1];
    expect(declared?.toLowerCase()).toBe(hex);
  });

  it("declares no colours outside the token set", () => {
    const declaredNames = [...css.matchAll(/--color-([a-z0-9-]+):\s*#/gi)].map((m) => m[1]);
    expect(declaredNames.sort()).toEqual(Object.keys(colors).sort());
  });
});

describe("every allowed colour pairing meets WCAG AA", () => {
  it.each(contrastRules.map((rule) => [rule.fg, rule.bg, rule.min, rule.use] as const))(
    "%s on %s is at least %s:1 (%s)",
    (fg, bg, min) => {
      expect(contrastRatio(hexToRgb(colors[fg]), background(bg))).toBeGreaterThanOrEqual(min);
    },
  );
});

describe("known failures stay out of the rules", () => {
  it("sand text on the deep-orange fill fails AA, so buttons switch to dark text", () => {
    expect(contrastRatio(hexToRgb(colors.text), hexToRgb(colors["accent-deep"]))).toBeLessThan(4.5);
    expect(contrastRules.some((r) => r.fg === "text" && r.bg === "accent-deep")).toBe(false);
  });

  it("hairlines are decorative only", () => {
    expect(contrastRules.some((r) => r.fg === "line")).toBe(false);
  });
});
