# Design system

RecallRadar's visual language follows the design reference (boonglobal.io, re-measured
2026-10-20): warm near-black, sand-coloured text, "sol" orange accents, glass surfaces, nested
hairline frames, a scroll-driven dot field, and calm, precise motion. We match the **style**, not the site: no logo, photography, copy, icons, source
code, or licensed fonts are reused.

Live gallery: **`/dev`** (not indexed). Source of truth: `apps/web/src/design/tokens.ts`, mirrored
in `apps/web/src/app/globals.css`; `tokens.test.ts` fails if they drift.

## Colour

| Token | Hex | On `bg-0` | Use |
|---|---|---|---|
| `bg-0` | `#010001` | — | Page background |
| `bg-1` | `#161210` | 1.13:1 | Raised surfaces |
| `line` | `#312c21` | 1.51:1 | Hairlines and dividers (decorative only) |
| `muted-3` | `#5e594a` | 2.998:1 | Decorative only (below the 3:1 needed for UI boundaries) |
| `muted-2` | `#959180` | 6.63:1 | Secondary text, input borders, *Couldn't identify* |
| `muted-1` | `#bbb8ab` | 10.54:1 | Secondary text |
| `khaki` | `#cdc9b5` | 12.60:1 | Tertiary text, hover borders |
| `text` | `#eeeadc` | 17.41:1 | Primary text (never pure white) |
| `accent` | `#ff9d00` | 10.06:1 | Highlights, *Check your unit*, focus rings, primary button |
| `accent-deep` | `#e34608` | 5.14:1 | *Recalled*, button hover fill |

**Contrast rules (WCAG 2.2 AA).** Every allowed pairing is listed in `contrastRules` and tested,
including text on translucent cards (composited over `bg-0`). Notable consequences:

- Sand on `accent-deep` is 3.39:1 (fails), so labels on the orange hover fill switch to `bg-0`
  (5.14:1). The reference keeps sand text there; we don't.
- Input borders use `muted-2`: `muted-3` is 2.998:1, just under WCAG 1.4.11's 3:1.
- `line` is decorative only. Nothing a user must perceive relies on it.

## Type

| Role | Face | Size | Line height | Tracking | Weight |
|---|---|---|---|---|---|
| Hero (`text-hero`) | Host Grotesk, uppercase | 56px @ 375w → 164px @ 1440w | 0.9 | −0.03em | 450 |
| Display (`text-display`) | Host Grotesk, uppercase | 36px → 88px | 0.9 | −0.027em | 450 |
| Verdict (`text-verdict`) | Host Grotesk, uppercase | 48px → 120px | 0.9 | −0.03em | 450 |
| Heading (`text-heading`) | Inter | 22px → 32px | 1.2 | −0.02em | 500 |
| Body (`text-body`) | Inter | 15px | 1.5 | −0.01em | 450 |
| Caption (`text-caption`) | Inter | 12px → 13.6px | 1.4 | +0.0075rem | 450 |
| Label / button (`text-label`) | Host Grotesk, uppercase | 15px | 1.1 | normal | 600 |
| Eyebrow (`eyebrow`) | Host Grotesk, uppercase | 12px | 1 | +0.02em | 600 |

Sizes are fluid `clamp()`s fitted to measurements of the reference at 375px and 1440px widths.

**Font choice.** The reference uses MSCHN and Suisse Int'l (both licensed). We compared free
Google Fonts at matched size, weight and tracking against crops of the reference:

- Display candidates: Archivo (widths 106, 112.5, 125), Space Grotesk, Lexend, Lexend Exa, Martian
  Mono, Sora, Familjen Grotesk, Red Hat Display, Host Grotesk, Geologica, Funnel Display.
- **Host Grotesk** won on proportions: width-to-cap-height of "CAUSE THE" is 6.47 against the
  reference's 6.5. Archivo and Sora ran about 12% wider, and Space Grotesk's quirky R and A read
  differently. The reference strokes are lighter, so we use weight 450, not 500.
- **Inter** was closer to Suisse Int'l than Geist, whose geometric forms read cooler.

Both are self-hosted by `next/font`; visitors' browsers never contact Google.

## Surfaces

- **Glass** (`.glass`): nav pills and the menu panel. `rgb(1 0 1 / 0.4)`, `blur(16px)`, 8px
  radius, no border.
- **Plain card** (`.card-plain`): the how-it-works cards. 1px `line` border, `rgb(22 18 16 /
  0.6)`, `blur(16px)`, 8px radius, 32px padding, 64px between icon and text; brightens to
  `rgb(49 44 33 / 0.45)` on hover (500ms, reveal easing).
- **Card** (`<Card>`): a card within a card. 1px `line` border, 4px padding, a 1px **dashed**
  inner frame, `rgb(49 44 33 / 0.3)`, `blur(16px)`, radii 8px and 4px. `floating` adds
  `0 10px 30px rgb(0 0 2 / 0.3)`.
- **Frame** (`<Frame>`): hairline outer frame inset 1rem, with a 3×3 dot-grid ornament in each
  corner, holding `.frame__panel` tiles (the footer).
- Without `backdrop-filter` support, glass and cards fall back to solid `bg-1`-based fills.

## Buttons and links

- **Outline** (default): transparent with a 20% `line` tint and a 1px inset hairline,
  `blur(17px)`, 4px radius, padding 1.067em × 1.6em, 15px/600 uppercase display face.
- **Primary**: filled `accent`, `bg-0` label. Use for the one main action on a screen.
- **Hover/press**: a `accent-deep` fill wipes up from the bottom (`clip-path`, 250ms, reveal
  easing). The leading arrow slides out right while a second slides in from the left. Hover effects
  apply only on devices that can hover; touch gets the fill on press.
- **Text link**: uppercase display face with an arrow and a 1px underline that fills with
  `accent` from the left on hover or focus (250ms).
- **Focus**: 2px `accent` outline, 3px offset, on everything focusable.

## Motion

| What | Duration | Easing |
|---|---|---|
| Hover colour | 150ms | linear |
| Menus, overlays, button wipe | 250ms | `cubic-bezier(0.5, 0.1, 0, 1)` |
| Reveals, menu height, page fade | 500ms | `cubic-bezier(0.5, 0.1, 0, 1)` |

- **Line reveal** (`<LineReveal>`): each line sits in a clipped mask and slides up, staggered
  80ms. `trigger="load"` is pure CSS (works without JS); `trigger="view"` arms only content that
  starts offscreen, so nothing visible is ever hidden after hydration.
- **Block reveal** (`<Reveal>`): cards and buttons fade and slide up 2rem as they enter view,
  staggered 80ms; same arming rule as line reveals.
- **Header** (measured on the reference): fixed 24px from the top, two 56px glass pills
  (wordmark, MENU), always in view.
- **Menu**: the label scrambles through block glyphs from MENU to CLOSE (≈330ms); the icon is a
  4×3 grid of 3px dots, 3px apart, keeping the six dots of a dotted × when open. The glass panel
  spans both pills, 8px below them, and opens by height (grid rows 0fr → 1fr, 500ms, reveal
  easing), uppercase 12px/600 links centred. Escape and outside clicks close it; focus moves
  into it on the first frame and back to the button on close.
- **Page transitions**: after a client-side navigation the new page fades in (500ms, opacity
  only, since a transform would break the field's fixed canvas). The first page of a visit
  doesn't fade; it has its own line reveals.
- **Smooth scroll**: Lenis, marketing pages only.

## The field (landing page)

One fixed WebGL2 canvas behind the landing page (`components/field/`), the reference's
signature effect rebuilt with our own shaders and imagery:

| Section | `data-field` | What the dots do |
|---|---|---|
| Hero, closing call to action | `panels` | Our procedural "imagery": domain-warped noise streaked like long exposures, graded black → ember → `accent-deep` → `accent` → sand with film grain, in a collage of hard-edged panels. Dissolves in 8px blocks into the dots as you scroll on. |
| First statement (3 screens, pinned) | `grid` | Halftone grid (14px apart, 18px on phones): dot size and colour follow a slow image of the same noise; moss-grey dots, orange where bright; twinkle |
| Second statement (2 screens, pinned) | `cloud` | A soft ball of orange dots, slowly turning |
| How it works | `torus` | A dotted torus seen near edge-on, 18 tube rings, turning |
| "No recall found never means safe." | `rings` | The radar: 9 dotted rings, 12px between dots, pulses running outward and a sweep |

- **Morphing**: a section holds its formation while it covers the viewport; during its last
  screen the dots move to the next one, each starting a little later than the last (up to 30%
  of the way), so the change ripples rather than snaps.
- **Text over the field** carries `data-field-shade` and the field darkens behind it (110px
  falloff) to a brightness cap: ember behind display type (`="large"`, 3:1 needed), darker
  behind body text (4.5:1). Dots dim only behind body text. Measured on the hero (worst of
  several frames, 1440×900): headline 5.99:1 sand and 3.46:1 orange, body 11.9:1, counter
  7.27:1; 375×812 is within 0.1. `e2e/field.spec.ts` reads the WebGL frame and enforces this.
- **Cost**: device pixel ratio capped at 1.5 (1.25 on phones); the panels render at half
  resolution and a composite pass adds grain at full size; the loop stops when the tab is
  hidden.
- **Reduced motion**: no loop and no morphing: still panels in the hero, a still grid elsewhere.
- **Without WebGL2**: panel sections show a CSS stand-in (warm glows at the edges).
- **Checking** (the check page): the WebGL radar sweep in a circle while a check runs, the CSS
  sweep as its fallback. App pages have no other WebGL: their headers sit on a still CSS dot
  matrix with an orange glow (`.page-dots`).

**Reduced motion** turns transitions off entirely, plays no reveal or scramble animations, and
disables Lenis and the radar (a static frame instead). We don't use the "0.01ms" trick: it makes
every element transition every property, including inherited `visibility`, which briefly hid the
menu from focus. Playwright runs the whole suite a second time with reduced motion on.

## Verdict states

The verdict is set in huge uppercase display type with an icon and an eyebrow, and every state
has words, so colour is never the only signal.

| State | Colour | Icon | Meaning (screen-reader text) |
|---|---|---|---|
| RECALLED | `accent-deep` | Triangle with ! | Matches an official recall by its exact identifier |
| CHECK YOUR UNIT | `accent` | Tag under a magnifier | The family matches, but only some models/lots/dates are covered |
| ALL CLEAR | `text` | Circle with ✓ | "No recalls found for this product in the sources we checked" |
| COULDN'T IDENTIFY | `muted-2` | Circle with ? | Needs a clearer photo or the model number |
| CAN'T CHECK YET | `muted-2` | Dashed circle | Product category not covered by our sources yet |

A unit test fails if any verdict copy ever calls a product "safe".

## Layout

- 16-column grid; gutters `clamp(0.5rem → 1rem)`, page margins `clamp(1.5rem → 7.5rem)`
  (`.page-x`).
- Breakpoints (from the reference): `sm` 768, `md` 940, `lg` 1100, `xl` 1200, `2xl` 1440.
- No horizontal scrolling at 375px; Playwright checks every page on a phone viewport.
