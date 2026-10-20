/*
 * Particle formations for the landing page's dot field. Every formation places the same N
 * particles, so the shader can morph between any two of them.
 *
 * Units: 1 = half the viewport height, origin at the viewport centre, y up, z towards the
 * viewer. The camera sits at z = CAMERA_DISTANCE, so z = 0 maps 1:1 onto the screen (the grid
 * lives there) and the 3D formations get a gentle perspective.
 */

export const CAMERA_DISTANCE = 3;

export const FORMATIONS = ["panels", "grid", "cloud", "torus", "rings"] as const;
export type Formation = (typeof FORMATIONS)[number];

export type Viewport = { width: number; height: number };

export type Particles = {
  count: number;
  /** One xyz triple per particle, per formation (the "panels" formation reuses the grid). */
  positions: Record<Exclude<Formation, "panels">, Float32Array>;
  /** 1 when the particle is a grid dot, 0 for spares hidden in the grid formation. */
  inGrid: Float32Array;
  /** 1 when the particle is a radar dot, 0 for spares hidden on the rings. */
  inRings: Float32Array;
  /** Per-particle random numbers in [0, 1): stagger, twinkle phase, colour pick. */
  seeds: Float32Array;
};

/** Grid spacing in CSS pixels: denser dots on large screens, as on the reference. */
export function gridSpacing({ width }: Viewport): number {
  return width < 768 ? 18 : width < 1200 ? 15 : 14;
}

/** Deterministic pseudo-random numbers, so a resize doesn't reshuffle the cloud. */
export function random(seed: number): () => number {
  let state = seed >>> 0 || 1;
  return () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return ((state >>> 0) % 1_000_000) / 1_000_000;
  };
}

/** Grid points covering the viewport (with one spare row and column), in world units. */
export function gridPoints(viewport: Viewport): Float32Array {
  const spacing = gridSpacing(viewport);
  const unit = viewport.height / 2;
  const cols = Math.ceil(viewport.width / spacing) + 1;
  const rows = Math.ceil(viewport.height / spacing) + 1;
  const points = new Float32Array(cols * rows * 3);
  const step = spacing / unit;
  const x0 = -((cols - 1) * step) / 2;
  const y0 = -((rows - 1) * step) / 2;
  let i = 0;
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      points[i++] = x0 + col * step;
      points[i++] = y0 + row * step;
      points[i++] = 0;
    }
  }
  return points;
}

/** A soft ball of dots, denser towards the middle. */
function cloud(count: number, next: () => number, aspect: number): Float32Array {
  const points = new Float32Array(count * 3);
  const radius = Math.min(0.95, 0.62 * aspect);
  for (let i = 0; i < count; i++) {
    // Direction uniform on the sphere; radius biased inwards (a cube root would be uniform).
    const u = next() * 2 - 1;
    const theta = next() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    const r = radius * Math.pow(next(), 0.6);
    points[i * 3] = r * s * Math.cos(theta) * 1.35;
    points[i * 3 + 1] = r * u * 0.85;
    points[i * 3 + 2] = r * s * Math.sin(theta);
  }
  return points;
}

/**
 * A torus seen almost edge-on: rings around the tube, so each reads as an upright ellipse and
 * together they make the wide dotted "tyre" that turns behind the how-it-works cards.
 */
function torus(count: number, aspect: number, rings = 24): Float32Array {
  const points = new Float32Array(count * 3);
  const major = Math.min(0.62, 0.45 * aspect);
  const minor = 0.4;
  const perRing = Math.ceil(count / rings);
  for (let i = 0; i < count; i++) {
    const ring = i % rings;
    const t = (Math.floor(i / rings) / perRing) * Math.PI * 2;
    const around = (ring / rings) * Math.PI * 2;
    const r = major + minor * Math.cos(t);
    points[i * 3] = r * Math.cos(around);
    points[i * 3 + 1] = minor * Math.sin(t);
    points[i * 3 + 2] = r * Math.sin(around);
  }
  return points;
}

/**
 * Concentric dotted rings facing the viewer: the radar. Dots sit a fixed distance apart along
 * each ring, as on the reference; particles left over wait hidden on the rings
 * (`visible` = 0) so they still have somewhere to morph to.
 */
function rings(
  count: number,
  aspect: number,
  next: () => number,
  ringCount = 6,
  spacing = 0.048,
): { points: Float32Array; visible: Float32Array } {
  const points = new Float32Array(count * 3);
  const visible = new Float32Array(count);
  const outer = Math.min(0.8, 0.62 * aspect);
  let i = 0;
  for (let k = 0; k < ringCount && i < count; k++) {
    const radius = outer * ((k + 1.5) / (ringCount + 0.5));
    const dots = Math.max(12, Math.round((Math.PI * 2 * radius) / spacing));
    for (let j = 0; j < dots && i < count; j++, i++) {
      const t = (j / dots) * Math.PI * 2 + k * 0.37;
      points[i * 3] = Math.cos(t) * radius;
      points[i * 3 + 1] = Math.sin(t) * radius;
      visible[i] = 1;
    }
  }
  const shown = i;
  for (; i < count; i++) {
    const from = Math.floor(next() * shown) * 3;
    points.set(points.subarray(from, from + 3), i * 3);
  }
  return { points, visible };
}

/** Every formation for the current viewport. At least `minimum` particles, so 3D shapes stay dense. */
export function buildParticles(viewport: Viewport, minimum = 4800): Particles {
  const grid = gridPoints(viewport);
  const gridCount = grid.length / 3;
  const count = Math.max(gridCount, minimum);
  const aspect = viewport.width / viewport.height;
  const next = random(0x5eed);

  const gridPositions = new Float32Array(count * 3);
  gridPositions.set(grid);
  const inGrid = new Float32Array(count);
  inGrid.fill(1, 0, gridCount);
  // Spares wait at random grid positions, invisible, so they morph out from the field.
  for (let i = gridCount; i < count; i++) {
    const from = Math.floor(next() * gridCount) * 3;
    gridPositions.set(grid.subarray(from, from + 3), i * 3);
  }

  const seeds = new Float32Array(count);
  for (let i = 0; i < count; i++) seeds[i] = next();
  const radar = rings(count, aspect, next);

  return {
    count,
    positions: {
      grid: gridPositions,
      cloud: cloud(count, next, aspect),
      torus: torus(count, aspect),
      rings: radar.points,
    },
    inGrid,
    inRings: radar.visible,
    seeds,
  };
}

export type Section = { formation: Formation; top: number; bottom: number };
export type FieldState = { from: Formation; to: Formation; t: number };

/**
 * Which formation the field shows at a scroll position. A section holds its formation while it
 * covers the viewport; the field morphs to the next one during the last screen of the section.
 */
export function fieldState(
  sections: Section[],
  scrollY: number,
  viewportHeight: number,
): FieldState {
  for (let i = 0; i < sections.length; i++) {
    const section = sections[i]!;
    const next = sections[i + 1];
    const hold = { from: section.formation, to: section.formation, t: 0 };
    if (!next) return hold;
    const morphStart = Math.max(section.top, section.bottom - viewportHeight);
    if (scrollY <= morphStart) return hold;
    if (scrollY < section.bottom) {
      const t = (scrollY - morphStart) / Math.max(1, section.bottom - morphStart);
      return { from: section.formation, to: next.formation, t };
    }
  }
  return { from: "panels", to: "panels", t: 0 };
}
