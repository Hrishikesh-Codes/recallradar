/**
 * Design tokens: the single source of truth. `globals.css` mirrors these values in Tailwind's
 * @theme block, and tokens.test.ts fails if the two drift or if a text pairing drops below
 * WCAG AA. Measured from the reference site; see docs/DESIGN.md.
 */

export const colors = {
  "bg-0": "#010001", // page background (near-black)
  "bg-1": "#161210", // raised surfaces
  line: "#312c21", // hairline borders and dividers (decorative only: 1.5:1)
  "muted-3": "#5e594a", // decorative only: 2.998:1, just under the 3:1 needed for UI boundaries
  "muted-2": "#959180", // secondary text
  "muted-1": "#bbb8ab",
  khaki: "#cdc9b5", // tertiary text, subtle fills
  text: "#eeeadc", // primary text: warm sand, never pure white
  accent: "#ff9d00", // "sol" orange: highlights, key words, active states, focus
  "accent-deep": "#e34608", // deep orange-red: RECALLED, button hover fill
} as const;

export type ColorToken = keyof typeof colors;

/** Translucent surfaces, as [colour, alpha]; contrast is checked against them composited on bg-0. */
export const surfaces = {
  glass: ["bg-0", 0.4],
  card: ["line", 0.3],
} as const satisfies Record<string, readonly [ColorToken, number]>;

export type ContrastRule = {
  fg: ColorToken;
  bg: ColorToken | keyof typeof surfaces;
  /** 4.5 for body text, 3 for large display text and non-text UI boundaries (WCAG 1.4.3/1.4.11). */
  min: 4.5 | 3;
  use: string;
};

/** Every foreground/background pairing the UI is allowed to use. */
export const contrastRules: readonly ContrastRule[] = [
  { fg: "text", bg: "bg-0", min: 4.5, use: "primary text" },
  { fg: "text", bg: "bg-1", min: 4.5, use: "primary text on raised surfaces" },
  { fg: "text", bg: "card", min: 4.5, use: "primary text on glass cards" },
  { fg: "khaki", bg: "bg-0", min: 4.5, use: "tertiary text" },
  { fg: "muted-1", bg: "bg-0", min: 4.5, use: "secondary text" },
  { fg: "muted-2", bg: "bg-0", min: 4.5, use: "secondary text, COULDN'T IDENTIFY" },
  { fg: "muted-2", bg: "bg-1", min: 4.5, use: "secondary text on raised surfaces" },
  { fg: "muted-2", bg: "card", min: 4.5, use: "card descriptions" },
  { fg: "accent", bg: "bg-0", min: 4.5, use: "highlighted words, CHECK YOUR UNIT, links" },
  { fg: "accent", bg: "card", min: 4.5, use: "highlights inside cards" },
  { fg: "accent-deep", bg: "bg-0", min: 4.5, use: "RECALLED" },
  { fg: "accent-deep", bg: "bg-1", min: 4.5, use: "RECALLED on raised surfaces" },
  { fg: "accent-deep", bg: "card", min: 4.5, use: "RECALLED status chip inside cards" },
  { fg: "bg-0", bg: "accent", min: 4.5, use: "primary button label" },
  { fg: "bg-0", bg: "accent-deep", min: 4.5, use: "button label on hover fill" },
  { fg: "muted-2", bg: "bg-0", min: 3, use: "input borders (non-text boundary)" },
  { fg: "accent", bg: "bg-1", min: 3, use: "focus ring on raised surfaces" },
];

export const easing = {
  /** Reveals, transforms, header show/hide. Measured on the reference. */
  reveal: "cubic-bezier(0.5, 0.1, 0, 1)",
} as const;

export const durations = {
  hover: 150,
  overlay: 250,
  reveal: 500,
} as const;
