import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { VerdictView } from "@/components/check/VerdictView";

// The Server Action module talks to the database; the view only needs it to exist.
vi.mock("@/app/list/actions", () => ({ saveItem: vi.fn() }));
import type { CheckResponse, MatchOut } from "@/lib/api/client";

const match: MatchOut = {
  tier: "check_unit",
  recall: {
    id: 1,
    source: "cpsc",
    source_label: "CPSC",
    source_recall_id: "10311",
    reference: "25338",
    notice_type: "recall",
    title: "More than One Million Anker Power Banks Recalled Due to Fire and Burn Hazards",
    hazard: "The lithium-ion battery in the power bank can overheat.",
    remedy: "Stop using the recalled power banks and contact Anker.",
    remedy_type: "replace",
    recall_date: "2025-06-12",
    status: "unknown",
    classification: null,
    firm: "Anker Innovations Limited",
    official_url: "https://www.cpsc.gov/Recalls/2025/example",
    image_url: null,
  },
  product: {
    product_name: "Anker PowerCore 10000 power banks (model A1263 only)",
    brand: "Anker Innovations Limited",
    model_numbers: ["A1263"],
    upcs: [],
    lot_codes: [],
    sold_start_date: null,
    sold_end_date: null,
    unit_restricted: true,
    restrictions: [{ kind: "serial", detail: "Only qualifying serial numbers are included." }],
    where_to_look: ['The model number "A1263" is printed on the bottom.'],
    quantity: null,
  },
  reasons: ["Model A1263 and the brand match CPSC recall 25338."],
  what_to_check: ["Only qualifying serial numbers are included."],
  similarity: 0.9,
};

const result: CheckResponse = {
  id: "00000000-0000-4000-8000-000000000000",
  verdict: "check_unit",
  query: {
    input_type: "text",
    product_name: "Anker PowerCore 10000 A1263",
    brand: null,
    model_numbers: ["A1263"],
    upcs: [],
    lot_codes: [],
    purchase_date: null,
    retailer: null,
    categories: [],
  },
  matches: [match],
  related: [],
  coverage: {
    checked: [
      { source: "cpsc", label: "CPSC", recalls: 1421, last_synced_at: null },
      { source: "fda_food", label: "FDA", recalls: 6412, last_synced_at: null },
    ],
    not_covered: [],
    recalls_checked: 7833,
    updated_at: null,
  },
  notes: [],
};

describe("VerdictView", () => {
  it("shows the verdict, the evidence, what to check, and the official notice", () => {
    render(<VerdictView result={result} onCheckAnother={() => {}} />);
    expect(screen.getByRole("heading", { level: 2, name: "Check your unit" })).toBeInTheDocument();
    expect(screen.getByText("Checked against 7,833 recalls from CPSC and FDA")).toBeInTheDocument();
    const card = screen.getByRole("article");
    expect(within(card).getByText(match.reasons[0]!)).toBeInTheDocument();
    expect(
      within(card).getByText("Only qualifying serial numbers are included."),
    ).toBeInTheDocument();
    expect(within(card).getByText(match.product.where_to_look[0]!)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: /official notice/i })).toHaveAttribute(
      "href",
      match.recall.official_url,
    );
  });

  it("says which agencies we can't check yet", () => {
    render(
      <VerdictView
        result={{
          ...result,
          verdict: "not_covered",
          matches: [],
          coverage: { ...result.coverage, not_covered: ["nhtsa"] },
        }}
        onCheckAnother={() => {}}
      />,
    );
    expect(screen.getByText(/NHTSA \(vehicles, car seats, tires\)/)).toBeInTheDocument();
  });

  it("offers feedback on each match", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<VerdictView result={result} onCheckAnother={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Not my product" }));
    expect(screen.getByRole("button", { name: "Not my product" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body)) as { label: string };
    expect(body.label).toBe("not_mine");
    vi.unstubAllGlobals();
  });
});
