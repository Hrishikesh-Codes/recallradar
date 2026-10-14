"use client";

import { useTransition } from "react";

import { removeItem, setDismissed } from "@/app/list/actions";
import { Card } from "@/components/ui/Card";
import { StatusChip } from "@/components/ui/StatusChip";
import type { Item } from "@/lib/api/server";
import { cn } from "@/lib/cn";
import { formatDate, timeAgo } from "@/lib/format";

export function ItemCard({ item }: { item: Item }) {
  const [pending, startTransition] = useTransition();
  return (
    <Card as="li" innerClassName={cn("flex flex-col gap-5 p-5", pending && "opacity-60")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-2">
          <h3 className="text-heading font-medium break-words">{item.label}</h3>
          <p className="text-caption text-muted-2">
            {item.input_type === "barcode" ? `Barcode ${item.input_value}` : item.input_value}
            {" · "}checked {timeAgo(item.last_checked_at)}
          </p>
        </div>
        <StatusChip verdict={item.verdict} />
      </div>

      {item.matches.length ? (
        <ul className="flex flex-col divide-y divide-line border-y border-line">
          {item.matches.map((match) => (
            <li
              key={match.recall.id}
              className={cn("flex flex-col gap-2 py-3", match.dismissed && "text-muted-2")}
            >
              <div className="flex flex-wrap items-center gap-2">
                {match.dismissed ? (
                  <span className="chip text-muted-2">Not mine</span>
                ) : (
                  <StatusChip verdict={match.tier} />
                )}
                <span className="eyebrow text-muted-2">
                  {match.recall.source_label} {match.recall.reference ?? ""}
                  {match.recall.recall_date ? ` · ${formatDate(match.recall.recall_date)}` : ""}
                </span>
              </div>
              <a
                href={match.recall.official_url}
                target="_blank"
                rel="noreferrer"
                className={cn("hover:text-accent", match.dismissed && "line-through")}
              >
                {match.recall.title}
                <span className="sr-only"> (official notice, opens in a new tab)</span>
              </a>
              <button
                type="button"
                disabled={pending}
                onClick={() =>
                  startTransition(() => setDismissed(item.id, match.recall.id, !match.dismissed))
                }
                className="chip cursor-pointer self-start px-3 py-2 text-muted-1 hover:text-text"
              >
                {match.dismissed ? "Undo: it might be mine" : "Not my product"}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <button
        type="button"
        disabled={pending}
        onClick={() => {
          if (window.confirm(`Remove “${item.label}” from your list?`)) {
            startTransition(() => removeItem(item.id));
          }
        }}
        className="self-start text-caption text-muted-2 underline underline-offset-4 hover:text-text"
      >
        Remove from list
      </button>
    </Card>
  );
}
