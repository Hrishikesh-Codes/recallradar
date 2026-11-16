"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/Button";

/** Shown when a page fails to render (most often: the recall service was asleep). */
export default function ErrorPage({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <section className="page-x flex min-h-svh flex-col justify-center gap-6 py-24">
      <p className="eyebrow text-muted-2">Something went wrong</p>
      <h1 className="display text-display">We couldn&apos;t load this</h1>
      <p className="max-w-prose text-muted-1">
        The recall service may be waking up, which takes up to a minute after a quiet spell. Nothing
        was lost. Try again.
      </p>
      <div>
        <Button variant="primary" onClick={reset}>
          Try again
        </Button>
      </div>
    </section>
  );
}
