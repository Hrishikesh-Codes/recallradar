import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { deleteAccount, signOut, updateAlerts } from "@/app/account/actions";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { getViewer, userFetch, type Me } from "@/lib/api/server";

export const metadata: Metadata = { title: "Account" };

async function Account({ searchParams }: { searchParams: PageProps<"/account">["searchParams"] }) {
  const viewer = await getViewer();
  if (!viewer) redirect("/sign-in?next=/account");
  const [me, params] = await Promise.all([userFetch<Me>(viewer.id, "/v1/me"), searchParams]);
  const tiers = new Set(me.settings.alert_tiers);
  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <p className="text-muted-1">
        {me.email ? (
          <>
            Signed in as <strong className="text-text">{me.email}</strong>.
          </>
        ) : (
          "This is a demo account. Sign in with your email to keep your list."
        )}{" "}
        {me.items} {me.items === 1 ? "item" : "items"} on your list.
      </p>

      <Card innerClassName="flex flex-col gap-5 p-5">
        <h2 className="eyebrow text-muted-2">Email alerts</h2>
        <form action={updateAlerts} className="flex flex-col gap-4">
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              name="email_alerts"
              defaultChecked={me.settings.email_alerts}
              disabled={me.is_anonymous}
              className="size-5 accent-[var(--color-accent)]"
            />
            Email me when a CPSC or NHTSA recall matches something on my list
          </label>
          <fieldset className="flex flex-col gap-2 pl-8" disabled={me.is_anonymous}>
            <legend className="mb-2 text-caption text-muted-2">For these verdicts</legend>
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                name="tier"
                value="recalled"
                defaultChecked={tiers.has("recalled")}
                className="size-4 accent-[var(--color-accent)]"
              />
              Recalled
            </label>
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                name="tier"
                value="check_unit"
                defaultChecked={tiers.has("check_unit")}
                className="size-4 accent-[var(--color-accent)]"
              />
              Check your unit
            </label>
          </fieldset>
          <p className="text-caption text-muted-2">
            FDA recalls aren&apos;t emailed: openFDA&apos;s terms rule out alerting the public with
            its data. They appear on your list instead.
          </p>
          <Button type="submit" className="self-start" disabled={me.is_anonymous}>
            Save alert settings
          </Button>
        </form>
      </Card>

      <Card innerClassName="flex flex-col gap-4 p-5">
        <h2 className="eyebrow text-muted-2">Your data</h2>
        <p className="text-muted-1">
          Download everything we hold about you: your account, list, matches, and alerts.
        </p>
        <a href="/account/export" className="text-link self-start" download>
          <span>Download my data (JSON)</span>
        </a>
      </Card>

      <Card innerClassName="flex flex-col gap-4 p-5">
        <h2 className="eyebrow text-muted-2">Delete account</h2>
        <p className="text-muted-1">
          Deletes your account, list, matches, and alert history at once. This can&apos;t be undone.
        </p>
        <form action={deleteAccount} className="flex flex-col gap-3">
          <label className="flex flex-col gap-2">
            <span className="text-caption text-muted-1">Type “delete” to confirm</span>
            <input name="confirm" className="field max-w-xs" autoComplete="off" required />
          </label>
          {params.error === "confirm" ? (
            <p role="alert" className="text-accent">
              Type “delete” to confirm.
            </p>
          ) : null}
          <Button type="submit" className="self-start">
            Delete everything
          </Button>
        </form>
      </Card>

      <form action={signOut}>
        <Button type="submit" arrow={false}>
          Sign out
        </Button>
      </form>
    </div>
  );
}

export default function AccountPage({ searchParams }: PageProps<"/account">) {
  return (
    <section className="page-x flex min-h-svh flex-col gap-12 pt-32 pb-24">
      <header>
        <p className="eyebrow mb-4 text-muted-2">Account</p>
        <h1 className="display text-display">Settings</h1>
      </header>
      <Suspense fallback={<p className="text-muted-2">Loading…</p>}>
        <Account searchParams={searchParams} />
      </Suspense>
    </section>
  );
}
