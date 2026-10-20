import { cn } from "@/lib/cn";

const COLS = 4;
const ROWS = 3;
// Dots that stay when the menu is open: the corners and the middle pair, a dotted ×.
const CLOSE = new Set(["0-0", "0-3", "1-1", "1-2", "2-0", "2-3"]);

/**
 * The menu button's icon, measured from the reference: a 4×3 grid of 3px dots with 3px gaps.
 * Open, only the six dots of a dotted × stay.
 */
export function MenuDots({ open, className }: { open: boolean; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("grid shrink-0 grid-cols-[repeat(4,3px)] gap-[3px]", className)}
    >
      {Array.from({ length: ROWS * COLS }, (_, i) => {
        const key = `${Math.floor(i / COLS)}-${i % COLS}`;
        return (
          <span
            key={key}
            className={cn(
              "size-[3px] rounded-full bg-current transition-opacity duration-(--dur-overlay) ease-reveal",
              open && !CLOSE.has(key) && "opacity-0",
            )}
          />
        );
      })}
    </span>
  );
}
