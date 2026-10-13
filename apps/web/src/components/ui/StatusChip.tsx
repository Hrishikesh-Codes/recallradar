import { VERDICTS, type Verdict } from "@/components/verdict";
import { cn } from "@/lib/cn";

export function StatusChip({ verdict, className }: { verdict: Verdict; className?: string }) {
  const { chip, colorClass, Icon, meaning } = VERDICTS[verdict];
  return (
    <span className={cn("chip", colorClass, className)} title={meaning}>
      <Icon className="size-3.5" />
      {chip}
    </span>
  );
}
