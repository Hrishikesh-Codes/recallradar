"use client";

import { MatchCard } from "@/components/check/MatchCard";
import { SaveButton } from "@/components/check/SaveButton";
import { ArrowRightIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { VerdictHeading } from "@/components/ui/VerdictHeading";
import type { CheckInput, CheckResponse, QueryOut } from "@/lib/api/client";
import { formatCount, listSources, timeAgo } from "@/lib/format";

const NOT_COVERED_NAMES: Record<string, string> = {
  nhtsa: "NHTSA (vehicles, car seats, tires)",
  fsis: "USDA FSIS (meat, poultry, and eggs)",
};

/** "Checked against 31,482 recalls from CPSC and FDA · updated 2 hours ago". */
export function CoverageLine({ coverage }: { coverage: CheckResponse["coverage"] }) {
  const sources = listSources(coverage.checked.map((s) => s.label));
  return (
    <p className="text-caption text-muted-2">
      Checked against {formatCount(coverage.recalls_checked)} recalls from {sources}
      {coverage.updated_at ? ` · updated ${timeAgo(coverage.updated_at)}` : ""}
    </p>
  );
}

function ReadAs({ query }: { query: QueryOut }) {
  const fields: Array<[string, string]> = [];
  if (query.product_name) fields.push(["Product", query.product_name]);
  if (query.brand) fields.push(["Brand", query.brand]);
  if (query.model_numbers.length) fields.push(["Model", query.model_numbers.join(", ")]);
  if (query.upcs.length)
    fields.push(["Barcode", query.upcs.map((u) => u.replace(/^0+/, "")).join(", ")]);
  if (query.lot_codes.length) fields.push(["Lot", query.lot_codes.join(", ")]);
  if (query.retailer) fields.push(["Store", query.retailer]);
  if (query.input_type === "vin") fields.push(["VIN", "Decoded by NHTSA, not stored"]);
  if (!fields.length) return null;
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-muted-1">
      {fields.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="eyebrow pt-1 text-muted-2">{label}</dt>
          <dd className="break-words">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function VerdictView({
  result,
  input,
  onCheckAnother,
}: {
  result: CheckResponse;
  /** What was checked, for "Save to my list". */
  input?: CheckInput;
  onCheckAnother: () => void;
}) {
  const uncovered = result.coverage.not_covered.map((s) => NOT_COVERED_NAMES[s] ?? s);
  return (
    <div className="flex flex-col gap-12">
      <div className="flex flex-col gap-4">
        <VerdictHeading verdict={result.verdict} as="h2" />
        <CoverageLine coverage={result.coverage} />
        {uncovered.length ? (
          <p className="max-w-prose text-muted-1">
            This looks like a product regulated by {listSources(uncovered)}, which we don&apos;t
            check yet. Search the agency&apos;s own site for now.
          </p>
        ) : null}
        {result.notes.map((note) => (
          <p key={note} className="max-w-prose text-muted-1">
            {note}
          </p>
        ))}
      </div>

      <Card innerClassName="flex flex-col gap-4 p-5">
        <h2 className="eyebrow text-muted-2">How we read it</h2>
        <ReadAs query={result.query} />
        <button type="button" onClick={onCheckAnother} className="text-link self-start">
          <ArrowRightIcon aria-hidden className="size-[0.8em]" />
          <span>Not right? Change it</span>
        </button>
      </Card>

      {result.matches.length ? (
        <section aria-labelledby="matches-heading" className="flex flex-col gap-4">
          <h2 id="matches-heading" className="eyebrow text-muted-2">
            {result.matches.length === 1 ? "The recall" : `${result.matches.length} recalls`}
          </h2>
          {result.matches.map((match) => (
            <MatchCard
              key={match.recall.id}
              match={match}
              checkId={result.id}
              verdict={result.verdict}
              query={result.query}
            />
          ))}
        </section>
      ) : null}

      {result.related.length ? (
        <section aria-labelledby="related-heading" className="flex flex-col gap-4">
          <div>
            <h2 id="related-heading" className="eyebrow text-muted-2">
              Similar recalls that don&apos;t match
            </h2>
            <p className="mt-2 text-caption text-muted-2">
              Different brand or product. Shown so you can rule them out yourself.
            </p>
          </div>
          <ul className="flex flex-col divide-y divide-line border-y border-line">
            {result.related.map((item) => (
              <li key={item.recall.id} className="py-3">
                <a
                  href={item.recall.official_url}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex items-baseline justify-between gap-4"
                >
                  <span className="group-hover:text-accent">{item.recall.title}</span>
                  <span className="eyebrow shrink-0 text-muted-2">
                    {item.recall.source_label} {item.recall.reference ?? ""}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="flex flex-wrap gap-3">
        {input && result.verdict !== "unidentified" ? <SaveButton input={input} /> : null}
        <Button variant="primary" onClick={onCheckAnother}>
          Check another product
        </Button>
      </div>
    </div>
  );
}
