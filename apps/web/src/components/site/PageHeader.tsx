import type { ReactNode } from "react";

import { LineReveal } from "@/components/motion/LineReveal";

/**
 * The top of an app page: eyebrow, a display headline that slides up line by line on load, and
 * an intro, over a still dot matrix in the reference's colours (CSS only: app screens stay
 * light, the WebGL field is for the landing page).
 */
export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  /** One string per line of the headline. */
  title: string[];
  children?: ReactNode;
}) {
  return (
    <header className="relative isolate max-w-3xl">
      <div aria-hidden className="page-dots" />
      <p className="eyebrow mb-4 text-muted-2">{eyebrow}</p>
      {/* A trailing space per line keeps the words apart in the heading's text. */}
      <LineReveal
        as="h1"
        trigger="load"
        className="display text-display"
        lines={title.map((line, i) => (i < title.length - 1 ? `${line} ` : line))}
      />
      {children ? <div className="mt-4 max-w-prose text-muted-1">{children}</div> : null}
    </header>
  );
}
