import type { Metadata } from "next";

import { ButtonLink } from "@/components/ui/Button";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <section className="page-x flex min-h-svh flex-col justify-center gap-6 py-24">
      <p className="eyebrow text-muted-2">404</p>
      <h1 className="display text-display">Nothing here</h1>
      <p className="max-w-prose text-muted-1">
        That page doesn&apos;t exist. You can still check a product.
      </p>
      <div className="flex flex-wrap gap-3">
        <ButtonLink href="/check" variant="primary">
          Check a product
        </ButtonLink>
        <ButtonLink href="/" arrow={false}>
          Home
        </ButtonLink>
      </div>
    </section>
  );
}
