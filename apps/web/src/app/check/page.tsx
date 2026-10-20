import type { Metadata } from "next";

import { CheckExperience } from "@/components/check/CheckExperience";
import { PageHeader } from "@/components/site/PageHeader";
import { getStats } from "@/lib/api/stats";

export const metadata: Metadata = {
  title: "Check a product",
  description: "Type, paste, or scan a product to see whether it has been recalled.",
};

export default async function CheckPage() {
  const stats = await getStats();
  return (
    <section className="page-x flex min-h-svh flex-col gap-12 pt-32 pb-24">
      <PageHeader eyebrow="Check a product" title={["Is it recalled?"]}>
        No account needed. We don&apos;t keep what you check, only that a check happened.
      </PageHeader>
      <div className="max-w-3xl">
        <CheckExperience recalls={stats?.recalls} />
      </div>
    </section>
  );
}
