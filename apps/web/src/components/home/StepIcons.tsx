import type { SVGProps } from "react";

/*
 * Animated line icons for the how-it-works cards, in the reference's manner: thin orange
 * strokes and dotted orbits that turn slowly. Our own drawings. Decorative; the animations
 * stop under reduced motion (globals.css).
 */

const BASE: SVGProps<SVGSVGElement> = {
  viewBox: "0 0 88 88",
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round",
  "aria-hidden": true,
};

/** A product seen from every side: a dotted globe whose meridians turn. */
export function ScanStepIcon({ className }: { className?: string }) {
  return (
    <svg {...BASE} className={className}>
      <circle cx="44" cy="44" r="30" strokeWidth="1.5" strokeDasharray="0.1 5.5" />
      <ellipse
        cx="44"
        cy="44"
        rx="22"
        ry="30"
        strokeWidth="1.2"
        strokeDasharray="0.1 4.5"
        className="step-icon__meridian"
      />
      <ellipse
        cx="44"
        cy="44"
        rx="22"
        ry="30"
        strokeWidth="1.2"
        strokeDasharray="0.1 4.5"
        className="step-icon__meridian step-icon__meridian--late"
      />
      <path d="M14 44h60" strokeWidth="1.2" strokeDasharray="0.1 4.5" />
      <circle
        cx="44"
        cy="44"
        r="2"
        fill="currentColor"
        stroke="none"
        className="step-icon__blink"
      />
    </svg>
  );
}

/** Checking every source: radar rings pulsing out from the centre. */
export function CheckStepIcon({ className }: { className?: string }) {
  return (
    <svg {...BASE} className={className}>
      <circle
        cx="44"
        cy="44"
        r="31"
        strokeWidth="1.5"
        strokeDasharray="0.1 4"
        className="step-icon__spin"
      />
      <circle cx="44" cy="44" r="21" strokeWidth="1.5" />
      <circle cx="44" cy="44" r="13" strokeWidth="1.5" />
      <circle cx="44" cy="44" r="13" strokeWidth="1.5" className="step-icon__pulse" />
      <circle cx="44" cy="44" r="3" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Watching your list: a tilted orbit with a dot that keeps going round. */
export function WatchStepIcon({ className }: { className?: string }) {
  return (
    <svg {...BASE} className={className}>
      <ellipse cx="44" cy="46" rx="30" ry="11" strokeWidth="1.5" strokeDasharray="0.1 4" />
      <ellipse cx="44" cy="40" rx="30" ry="11" strokeWidth="1.2" strokeOpacity="0.55" />
      <path d="M44 18v52" strokeWidth="1.5" />
      {/* Rotating inside a squashed group traces the ellipse. */}
      <g transform="translate(44 43) scale(1 0.37)">
        <g className="step-icon__orbit">
          <circle cx="30" cy="0" r="3" fill="currentColor" stroke="none" />
        </g>
      </g>
    </svg>
  );
}
