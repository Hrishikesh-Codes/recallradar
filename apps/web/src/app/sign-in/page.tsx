import type { Metadata } from "next";
import { Suspense } from "react";

import { DemoButton } from "@/components/account/DemoButton";
import { SignInForm } from "@/components/account/SignInForm";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in with an email link to keep a list of what you own.",
};

async function Form({ searchParams }: { searchParams: PageProps<"/sign-in">["searchParams"] }) {
  const params = await searchParams;
  const next = typeof params.next === "string" ? params.next : null;
  return (
    <>
      {params.error ? (
        <p role="alert" className="text-accent">
          That link didn&apos;t work. It may have expired or been used already. Ask for a new one.
        </p>
      ) : null}
      <SignInForm next={next} />
    </>
  );
}

export default function SignInPage({ searchParams }: PageProps<"/sign-in">) {
  return (
    <section className="page-x flex min-h-svh flex-col gap-12 pt-32 pb-24">
      <header className="max-w-3xl">
        <p className="eyebrow mb-4 text-muted-2">My list</p>
        <h1 className="display text-display text-balance">Keep watch on what you own</h1>
        <p className="mt-4 max-w-prose text-muted-1">
          Save products to a list. We re-check them every day and email you if a CPSC or NHTSA
          recall matches one. FDA recalls show up on your list.
        </p>
      </header>
      <div className="flex max-w-md flex-col gap-6">
        <Suspense>
          <Form searchParams={searchParams} />
        </Suspense>
      </div>
      <div className="flex max-w-md flex-col gap-3 border-t border-line pt-8">
        <p className="text-muted-1">Just looking? Try a sample list. No email needed.</p>
        <DemoButton />
      </div>
    </section>
  );
}
