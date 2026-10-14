import { formatCount } from "@/lib/format";

/** Shown while a check runs: a radar sweep (static under reduced motion) and what we're doing. */
export function Checking({ recalls }: { recalls?: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col items-start gap-8">
      <div aria-hidden className="radar-sweep" />
      <div>
        <p className="display text-display">Checking</p>
        <p className="mt-3 text-muted-1">
          {recalls
            ? `Matching against ${formatCount(recalls)} official recalls…`
            : "Matching against official recall notices…"}
        </p>
      </div>
    </div>
  );
}
