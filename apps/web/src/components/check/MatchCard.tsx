"use client";

import { useState } from "react";

import { ArrowRightIcon } from "@/components/icons";
import { Card } from "@/components/ui/Card";
import { StatusChip } from "@/components/ui/StatusChip";
import {
  sendFeedback,
  type CheckResponse,
  type FeedbackLabel,
  type MatchOut,
  type QueryOut,
} from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/format";

const FEEDBACK: ReadonlyArray<{ label: FeedbackLabel; text: string }> = [
  { label: "mine", text: "This is mine" },
  { label: "not_mine", text: "Not my product" },
  { label: "handled", text: "Already handled" },
];

// FDA safety warnings and USDA FSIS public health alerts are official notices, but not recalls:
// FSIS issues an alert when product can't be recalled, often because it's no longer for sale.
const NOTICE_KINDS: Record<MatchOut["recall"]["notice_type"], { name: string; chip?: string }> = {
  recall: { name: "recall" },
  warning: { name: "warning", chip: "Warning, not a recall" },
  alert: { name: "public health alert", chip: "Public health alert, not a recall" },
};

function Section({ title, items }: { title: string; items: readonly string[] }) {
  const unique = [...new Set(items)];
  if (!unique.length) return null;
  return (
    <div>
      <h4 className="eyebrow mb-2 text-muted-2">{title}</h4>
      <ul className="flex flex-col gap-1.5 text-muted-1">
        {unique.map((item) => (
          <li key={item} className="flex gap-2">
            <span aria-hidden className="mt-[0.6em] size-1 shrink-0 rounded-full bg-accent" />
            <span className="break-words">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Feedback({ onSend }: { onSend: (label: FeedbackLabel) => Promise<unknown> }) {
  const [sent, setSent] = useState<FeedbackLabel | null>(null);
  const [failed, setFailed] = useState(false);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Is this your product?">
        {FEEDBACK.map(({ label, text }) => (
          <button
            key={label}
            type="button"
            aria-pressed={sent === label}
            onClick={() => {
              setSent(label);
              setFailed(false);
              onSend(label).catch(() => setFailed(true));
            }}
            className={cn(
              "chip cursor-pointer px-3 py-2 transition-colors",
              sent === label ? "bg-text text-bg-0" : "text-muted-1 hover:text-text",
            )}
          >
            {text}
          </button>
        ))}
      </div>
      <p className="text-caption text-muted-2" aria-live="polite">
        {failed
          ? "We couldn't save that. Try again in a moment."
          : sent
            ? "Thanks. Answers like this teach the matcher."
            : ""}
      </p>
    </div>
  );
}

export function MatchCard({
  match,
  checkId,
  verdict,
  query,
}: {
  match: MatchOut;
  checkId: string;
  verdict: CheckResponse["verdict"];
  query: QueryOut;
}) {
  const { recall, product } = match;
  const kind = NOTICE_KINDS[recall.notice_type];
  const reference = `${recall.source_label} ${kind.name} ${recall.reference ?? recall.source_recall_id}`;
  const toCheck = [...match.what_to_check];
  if (match.tier === "check_unit") {
    for (const tip of product.where_to_look) if (!toCheck.includes(tip)) toCheck.push(tip);
  }
  return (
    <Card as="article" innerClassName="flex flex-col gap-6 p-5 md:p-6">
      <header className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {match.tier ? <StatusChip verdict={match.tier} /> : null}
            {kind.chip ? <span className="chip text-muted-1">{kind.chip}</span> : null}
          </div>
          <h3 className="text-heading font-medium text-balance">{recall.title}</h3>
          <p className="eyebrow text-muted-2">
            {reference}
            {recall.recall_date ? ` · ${formatDate(recall.recall_date)}` : ""}
            {recall.classification && recall.classification.toLowerCase() !== kind.name
              ? ` · ${recall.classification}`
              : ""}
          </p>
        </div>
        {recall.image_url ? (
          // Official notice photos (public domain); external, so not optimized by next/image.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={recall.image_url}
            alt={`Photo from the official notice: ${product.product_name}`}
            loading="lazy"
            className="aspect-square w-28 shrink-0 rounded-sm bg-khaki object-contain md:w-36"
          />
        ) : null}
      </header>

      <Section title="Why it matched" items={match.reasons} />
      <Section title="What to check" items={toCheck} />
      <Section title="Hazard" items={recall.hazard ? [recall.hazard] : []} />
      <Section title="What to do" items={recall.remedy ? [recall.remedy] : []} />

      {recall.official_url ? (
        <a
          href={recall.official_url}
          target="_blank"
          rel="noreferrer"
          className="text-link self-start"
        >
          <ArrowRightIcon aria-hidden className="size-[0.8em]" />
          <span>Official notice</span>
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      ) : null}

      <Feedback
        onSend={(label) =>
          sendFeedback({
            check_id: checkId,
            recall_id: recall.id,
            label,
            tier_shown: match.tier ?? verdict,
            query,
          })
        }
      />
    </Card>
  );
}
