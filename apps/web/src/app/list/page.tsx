import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { ListView } from "@/components/account/ListView";
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
      <header className="max-w-3xl">
        <p className="eyebrow mb-4 text-muted-2">My list</p>
        <h1 className="display text-display text-balance">What you own</h1>
        <p className="mt-4 max-w-prose text-muted-1">
          Re-checked every day against new recalls. If one matches, you get an email for CPSC
          recalls, and every match shows here.
        </p>
      </header>
      <Suspense fallback={<p className="text-muted-2">Loading your list…</p>}>
        <List />
      </Suspense>
    </section>
  );
}
