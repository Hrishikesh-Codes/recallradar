import { cn } from "@/lib/cn";

const POSITIONS = [0, 1, 2].flatMap((row) => [0, 1, 2].map((col) => ({ row, col })));

/**
 * 3×3 dot grid. As the menu icon it morphs into an X (`crossed`): the four edge-centre dots
 * fade out and the corners pull in toward the centre.
 */
export function DotGrid({ crossed = false, className }: { crossed?: boolean; className?: string }) {
  return (
    <svg
      viewBox="0 0 14 14"
      width="1em"
      height="1em"
      aria-hidden
      className={cn("shrink-0", className)}
      fill="currentColor"
    >
      {POSITIONS.map(({ row, col }) => {
        const isEdgeCentre = (row + col) % 2 === 1;
        const isCorner = row !== 1 && col !== 1;
        const pull =
          crossed && isCorner ? `translate(${(1 - col) * 1.5}px, ${(1 - row) * 1.5}px)` : "none";
        return (
          <circle
            key={`${row}-${col}`}
            cx={2 + col * 5}
            cy={2 + row * 5}
            r={1.25}
            style={{
              transform: pull,
              opacity: crossed && isEdgeCentre ? 0 : 1,
              transition:
                "transform var(--dur-overlay) var(--ease-reveal), opacity var(--dur-overlay) linear",
            }}
          />
        );
      })}
    </svg>
  );
}
