import { VERDICTS, type Verdict } from "@/components/verdict";
import { cn } from "@/lib/cn";

/**
 * The verdict in huge uppercase display type, with an icon and an eyebrow label. The words slide
 * up from behind a mask when it appears, like the reference's headlines.
 */
export function VerdictHeading({
  verdict,
  as: Heading = "h1",
  className,
}: {
  verdict: Verdict;
  as?: "h1" | "h2" | "h3";
  className?: string;
}) {
  const { label, colorClass, Icon, meaning } = VERDICTS[verdict];
  return (
    <div className={cn(colorClass, className)} data-verdict={verdict}>
      <p className="eyebrow mb-4 flex items-center gap-2">
        <Icon className="size-5" />
        <span>Verdict</span>
      </p>
      <Heading className="display text-verdict" data-reveal="on-load">
        <span className="reveal-line">
          <span className="reveal-line__inner">{label}</span>
        </span>
      </Heading>
      <p className="mt-4 max-w-prose text-muted-1">{meaning}</p>
    </div>
  );
}
