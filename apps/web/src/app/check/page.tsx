import type { Metadata } from "next";

import { CheckExperience } from "@/components/check/CheckExperience";
import { getStats } from "@/lib/api/stats";

export const metadata: Metadata = {
  title: "Check a product",
  description: "Type, paste, or scan a product to see whether it has been recalled.",
};

export default async function CheckPage() {
  const stats = await getStats();
  return (
    <section className="page-x flex min-h-svh flex-col gap-12 pt-32 pb-24">
      <header className="max-w-3xl">
        <p className="eyebrow mb-4 text-muted-2">Check a product</p>
        <h1 className="display text-display text-balance">Is it recalled?</h1>
        <p className="mt-4 max-w-prose text-muted-1">
          No account needed. We don&apos;t keep what you check, only that a check happened.
        </p>
      </header>
      <div className="max-w-3xl">
        <CheckExperience recalls={stats?.recalls} />
      </div>
    </section>
  );
}
