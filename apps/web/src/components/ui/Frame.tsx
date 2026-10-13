import type { ReactNode } from "react";

import { DotGrid } from "@/components/ui/DotGrid";
import { cn } from "@/lib/cn";

const CORNERS = ["top-8 left-8", "top-8 right-8", "bottom-8 left-8", "bottom-8 right-8"];

/** Hairline outer frame with a dot-grid ornament in each corner (the reference footer style). */
export function Frame({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("frame", className)}>
      {CORNERS.map((position) => (
        <DotGrid key={position} className={cn("frame__corner text-[0.875rem]", position)} />
      ))}
      <div className="relative z-10">{children}</div>
    </div>
  );
}
