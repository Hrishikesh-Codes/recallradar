import type { ReactNode } from "react";

import type { Formation } from "@/components/field/formations";
import { Reveal } from "@/components/motion/Reveal";
import { cn } from "@/lib/cn";

export type Note = { text: string; side: "left" | "right"; at: number };

/**
 * A statement pinned in the middle of the screen while the section scrolls past, as on the
 * reference: the section is several screens tall, the statement sticks, and short notes drift
 * up past it. The notes are plain text under a short orange rule (no boxes); they fade up as
 * they arrive and the dots dim behind them. `at` places a note down the section (0–1).
 */
export function StickyStatement({
  field,
  screens,
  notes = [],
  children,
  id,
}: {
  field: Formation;
  screens: number;
  notes?: Note[];
  children: ReactNode;
  id?: string;
}) {
  return (
    <section
      id={id}
      data-field={field}
      className="relative z-[1]"
      style={{ height: `${screens * 100}svh` }}
    >
      <div className="page-x sticky top-0 flex h-svh flex-col items-center justify-center text-center">
        {children}
      </div>
      {notes.length ? (
        <ul aria-label="Notes" className="page-x pointer-events-none absolute inset-0">
          {notes.map((note) => (
            <li
              key={note.text}
              className={cn(
                "absolute w-[min(17.5rem,72vw)]",
                note.side === "left" ? "left-(--margin)" : "right-(--margin)",
              )}
              style={{ top: `${note.at * 100}%` }}
            >
              <Reveal>
                <div data-field-shade>
                  <span aria-hidden className="mb-4 block h-px w-8 bg-accent" />
                  <p className="text-text">{note.text}</p>
                </div>
              </Reveal>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
