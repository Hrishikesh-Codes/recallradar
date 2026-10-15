import type { Metadata } from "next";

export const metadata: Metadata = { title: "Offline" };

/** Shown by the service worker when a page can't load. */
export default function OfflinePage() {
  return (
    <section className="page-x flex min-h-svh flex-col justify-center gap-6 py-24">
      <h1 className="display text-display">You&apos;re offline</h1>
      <p className="max-w-prose text-muted-1">
        Checks need a connection, so we can compare against the latest recalls. Reconnect and try
        again. Your list is safe.
      </p>
    </section>
  );
}
