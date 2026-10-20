import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { ListView } from "@/components/account/ListView";
import { PageHeader } from "@/components/site/PageHeader";
import { getViewer, userFetch, type Item } from "@/lib/api/server";

export const metadata: Metadata = {
  title: "My list",
  description: "The products you own, re-checked against new recalls every day.",
};

async function List() {
  const viewer = await getViewer();
  if (!viewer) redirect("/sign-in?next=/list");
  const items = await userFetch<Item[]>(viewer.id, "/v1/me/items");
  return <ListView items={items} isAnonymous={viewer.isAnonymous} />;
}

export default function ListPage() {
  return (
    <section className="page-x flex min-h-svh flex-col gap-12 pt-32 pb-24">
      <PageHeader eyebrow="My list" title={["What you own"]}>
        Re-checked every day against new recalls. If one matches, you get an email for CPSC, NHTSA
        and USDA recalls, and every match shows here.
      </PageHeader>
      <Suspense fallback={<p className="text-muted-2">Loading your list…</p>}>
        <List />
      </Suspense>
    </section>
  );
}
