import { RadarField } from "@/components/home/RadarField";
import { formatCount } from "@/lib/format";

const CENTRE: [number, number] = [0.5, 0.5];

/**
 * Shown while a check runs: the radar (WebGL; a still frame under reduced motion, the CSS sweep
 * without WebGL2) and what we're doing. `waking`: the check is slow because the API host was
 * asleep.
 */
export function Checking({ recalls, waking = false }: { recalls?: number; waking?: boolean }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col items-start gap-8">
      <div aria-hidden className="radar-sweep">
        <RadarField origin={CENTRE} compact className="radar-field--round absolute inset-0" />
      </div>
      <div>
        <p className="display text-display">Checking</p>
        <p className="mt-3 text-muted-1">
          {recalls
            ? `Matching against ${formatCount(recalls)} official recalls…`
            : "Matching against official recall notices…"}
        </p>
        {waking ? (
          <p className="mt-3 max-w-prose text-muted-2">
            Waking the recall service. The first check after a quiet spell can take up to a minute;
            it&apos;s quick after that.
          </p>
        ) : null}
      </div>
    </div>
  );
}
