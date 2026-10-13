import { useId, type ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/cn";

/** Labelled text input. The label is always rendered (visually hidden if `hideLabel`). */
export function TextField({
  label,
  hint,
  hideLabel = false,
  className,
  id,
  ...props
}: {
  label: string;
  hint?: string;
  hideLabel?: boolean;
} & ComponentPropsWithoutRef<"input">) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <label htmlFor={inputId} className={cn("eyebrow text-muted-1", hideLabel && "sr-only")}>
        {label}
      </label>
      <input id={inputId} aria-describedby={hintId} className="field" {...props} />
      {hint ? (
        <p id={hintId} className="text-caption text-muted-2">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
