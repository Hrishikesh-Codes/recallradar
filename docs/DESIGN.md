# Design system

RecallRadar's visual language follows the design reference (boonglobal.io): warm near-black,
sand-coloured text, "sol" orange accents, glass surfaces, nested hairline frames, and calm,
precise motion. We match the **style**, not the site: no logo, photography, copy, icons, source
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
| Reveals, header show/hide | 500ms | `cubic-bezier(0.5, 0.1, 0, 1)` |

- **Line reveal** (`<LineReveal>`): each line sits in a clipped mask and slides up, staggered
  80ms. `trigger="load"` is pure CSS (works without JS); `trigger="view"` arms only content that
  starts offscreen, so nothing visible is ever hidden after hydration.
- **Menu**: the label scrambles through block glyphs from MENU to CLOSE; the 3×3 dot icon becomes
  an X; the glass panel fades and drops 8px, its items staggered 40ms. Escape and outside clicks
  close it, focus moves into it on open and back to the button on close.
- **Header**: hides while scrolling down past 120px; returns on scroll up or keyboard focus.
- **Smooth scroll**: Lenis, marketing pages only.
- **Radar** (M1): a WebGL2 halftone dot field with pulse rings and a sweep, on the landing hero
  and the "checking" state only, paused offscreen, device pixel ratio capped.

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
