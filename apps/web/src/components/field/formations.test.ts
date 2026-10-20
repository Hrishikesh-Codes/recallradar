import {
  buildParticles,
  fieldState,
  gridPoints,
  gridSpacing,
  type Section,
} from "@/components/field/formations";

const DESKTOP = { width: 1440, height: 900 };
const PHONE = { width: 375, height: 812 };

describe("gridPoints", () => {
  it("covers the viewport edge to edge at the measured spacing", () => {
    const points = gridPoints(DESKTOP);
    const spacing = gridSpacing(DESKTOP);
    const xs = Array.from(points.filter((_, i) => i % 3 === 0));
    const unit = DESKTOP.height / 2;
    // World units back to CSS pixels: the grid spans at least the full width.
    expect((Math.max(...xs) - Math.min(...xs)) * unit).toBeGreaterThanOrEqual(DESKTOP.width);
    expect((xs[1]! - xs[0]!) * unit).toBeCloseTo(spacing, 5);
  });

  it("uses larger spacing on phones", () => {
    expect(gridSpacing(PHONE)).toBeGreaterThan(gridSpacing(DESKTOP));
  });
});

describe("buildParticles", () => {
  it("gives every formation the same particles, and keeps 3D shapes dense on phones", () => {
    const particles = buildParticles(PHONE);
    expect(particles.count).toBeGreaterThanOrEqual(4800);
    for (const positions of Object.values(particles.positions)) {
      expect(positions).toHaveLength(particles.count * 3);
      expect(positions.every(Number.isFinite)).toBe(true);
    }
    const gridDots = gridPoints(PHONE).length / 3;
    expect(particles.inGrid.reduce((a, b) => a + b, 0)).toBe(gridDots);
  });

  it("is deterministic, so a resize doesn't reshuffle the field", () => {
    expect(buildParticles(DESKTOP).positions.cloud).toEqual(
      buildParticles(DESKTOP).positions.cloud,
    );
  });

  it("keeps the 3D formations on screen", () => {
    const particles = buildParticles(DESKTOP);
    const aspect = DESKTOP.width / DESKTOP.height;
    for (const name of ["cloud", "torus", "rings"] as const) {
      const p = particles.positions[name];
      for (let i = 0; i < particles.count; i++) {
        expect(Math.abs(p[i * 3]!)).toBeLessThan(aspect);
        expect(Math.abs(p[i * 3 + 1]!)).toBeLessThan(1);
      }
    }
  });
});

describe("fieldState", () => {
  const vh = 900;
  const sections: Section[] = [
    { formation: "panels", top: 0, bottom: 900 },
    { formation: "grid", top: 900, bottom: 3600 },
    { formation: "cloud", top: 3600, bottom: 5400 },
  ];

  it("holds the hero's panels at the top", () => {
    expect(fieldState(sections, 0, vh)).toEqual({ from: "panels", to: "panels", t: 0 });
  });

  it("morphs during the last screen of a section", () => {
    expect(fieldState(sections, 450, vh)).toEqual({ from: "panels", to: "grid", t: 0.5 });
    expect(fieldState(sections, 3150, vh)).toEqual({ from: "grid", to: "cloud", t: 0.5 });
  });

  it("holds a tall section's formation while it is pinned", () => {
    expect(fieldState(sections, 1800, vh)).toEqual({ from: "grid", to: "grid", t: 0 });
  });

  it("keeps the last formation past the end", () => {
    expect(fieldState(sections, 9000, vh)).toEqual({ from: "cloud", to: "cloud", t: 0 });
  });
});
