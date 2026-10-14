import { startDemo } from "@/app/list/actions";
import { Button } from "@/components/ui/Button";

/** "Try the demo": a private sample list, no email needed. */
export function DemoButton({ variant = "outline" }: { variant?: "outline" | "primary" }) {
  return (
    <form action={startDemo}>
      <Button type="submit" variant={variant}>
        Try the demo
      </Button>
    </form>
  );
}
