"use client";

import { useEffect, useRef, useState, useTransition } from "react";

import { saveItem } from "@/app/list/actions";
import { ItemCard } from "@/components/account/ItemCard";
import { CheckForm } from "@/components/check/CheckForm";
import type { CheckInput } from "@/lib/api/client";
import type { Item } from "@/lib/api/server";
import { takePendingSave } from "@/lib/pendingCheck";

const ATTENTION = new Set(["recalled", "check_unit"]);

export function ListView({ items, isAnonymous }: { items: Item[]; isAnonymous: boolean }) {
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState<string | null>(null);
  const pendingSave = useRef<CheckInput | null | undefined>(undefined);

  function add(input: CheckInput) {
    setMessage(null);
    startTransition(async () => {
      const result = await saveItem(input);
      if (result.status === "saved") setMessage(`Saved “${result.item.label}”.`);
      else if (result.status === "error") setMessage(result.message);
      else setMessage("Your session ended. Sign in again to save.");
    });
  }

  // A "Save to my list" that started before sign-in finishes here.
  useEffect(() => {
    if (pendingSave.current === undefined) pendingSave.current = takePendingSave();
    const input = pendingSave.current;
    if (!input) return;
    const timer = window.setTimeout(() => {
      pendingSave.current = null;
      add(input);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const attention = items.filter((item) => ATTENTION.has(item.verdict)).length;
  return (
    <div className="flex flex-col gap-12">
      {isAnonymous ? (
        <p className="max-w-prose text-muted-1">
          This is a private demo list with real examples. Nothing here is emailed.{" "}
          <a href="/sign-in?next=/list" className="text-accent underline underline-offset-4">
            Sign in with your email
          </a>{" "}
          to keep it and get alerts.
        </p>
      ) : null}

      <p className="display text-heading" role="status">
        {items.length === 0
          ? "Your list is empty"
          : `We checked ${items.length} ${items.length === 1 ? "item" : "items"}${
              attention
                ? ` · ${attention} ${attention === 1 ? "needs" : "need"} your attention`
                : ""
            }`}
      </p>

      {items.length ? (
        <ul className="flex flex-col gap-4">
          {items.map((item) => (
            <ItemCard key={item.id} item={item} />
          ))}
        </ul>
      ) : null}

      <section aria-labelledby="add-heading" className="flex max-w-3xl flex-col gap-6">
        <h2 id="add-heading" className="eyebrow text-muted-2">
          Add something you own
        </h2>
        <CheckForm onSubmit={add} disabled={pending} submitLabel="Save to my list" />
        <p className="text-caption text-muted-1" aria-live="polite">
          {pending ? "Checking and saving…" : message}
        </p>
      </section>
    </div>
  );
}
