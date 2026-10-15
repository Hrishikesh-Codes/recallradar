import { expect, test, type Page } from "@playwright/test";

/*
 * The check flow in the browser. The API is mocked here (its own tests run against real
 * recalls), so this covers the page: input, checking state, verdict, evidence, feedback.
 */
const RESULT = {
  id: "00000000-0000-4000-8000-000000000000",
  verdict: "recalled",
  query: {
    input_type: "text",
    product_name: "Peloton bike PL01",
    brand: null,
    model_numbers: ["PL01"],
    upcs: [],
    lot_codes: [],
    purchase_date: null,
    retailer: null,
    categories: [],
  },
  matches: [
    {
      tier: "recalled",
      recall: {
        id: 42,
        source: "cpsc",
        source_label: "CPSC",
        source_recall_id: "9621",
        reference: "23201",
        notice_type: "recall",
        title: "Peloton Recalls Two Million Exercise Bikes Due to Fall and Injury Hazards",
        hazard: "The seat post can break during use.",
        remedy: "Stop using the bikes and contact Peloton for a free replacement seat post.",
        remedy_type: "repair",
        recall_date: "2023-05-11",
        status: "unknown",
        classification: null,
        firm: "Peloton",
        official_url: "https://www.cpsc.gov/Recalls/2023/example",
        image_url: null,
      },
      product: {
        product_name: "Peloton Bikes Model PL01",
        brand: "Peloton",
        model_numbers: ["PL01"],
        upcs: [],
        lot_codes: [],
        sold_start_date: null,
        sold_end_date: null,
        unit_restricted: false,
        restrictions: [],
        where_to_look: [],
        quantity: null,
      },
      reasons: ["Model PL01 and the brand match CPSC recall 23201."],
      what_to_check: [],
      similarity: 0.93,
    },
  ],
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

async function mockApi(page: Page) {
  const checks: unknown[] = [];
  const feedback: unknown[] = [];
  await page.route("**/v1/check", async (route) => {
    checks.push(route.request().postDataJSON());
    await route.fulfill({ json: RESULT });
  });
  await page.route("**/v1/feedback", async (route) => {
    feedback.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: { status: "accepted" } });
  });
  return { checks, feedback };
}

test("type a product and get a verdict with its evidence", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/check");
  await page.getByLabel("What is it?").fill("Peloton bike PL01");
  await page.getByRole("button", { name: "Check it" }).click();

  await expect(page.getByRole("heading", { level: 2, name: "Recalled" })).toBeVisible();
  await expect(page.getByText("Checked against 7,833 recalls from CPSC and FDA")).toBeVisible();
  const card = page.getByRole("article");
  await expect(card.getByText("Model PL01 and the brand match CPSC recall 23201.")).toBeVisible();
  await expect(card.getByRole("link", { name: /official notice/i })).toHaveAttribute(
    "href",
    "https://www.cpsc.gov/Recalls/2023/example",
  );
  expect(api.checks).toEqual([
    { input: { type: "text", value: "Peloton bike PL01" }, purchase_date: null },
  ]);

  await card.getByRole("button", { name: "This is mine" }).click();
  await expect(card.getByText(/teach the matcher/)).toBeVisible();
  expect(api.feedback).toHaveLength(1);
});

test("Try it now on the home page runs the check on /check", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/");
  await page.getByLabel("Product, link, barcode digits, or VIN").fill("Peloton bike PL01");
  await page.getByRole("button", { name: "Check", exact: true }).click();
  await expect(page).toHaveURL(/\/check$/);
  await expect(page.getByRole("heading", { level: 2, name: "Recalled" })).toBeVisible();
  // The product text travels in session storage, never in the URL.
  expect(page.url()).not.toContain("Peloton");
  expect(api.checks).toHaveLength(1);
});

test("links, barcodes, and VINs are read as such", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/check");
  await page.getByRole("tab", { name: "Paste a link" }).click();
  await page.getByLabel("Product link").fill("https://www.amazon.com/Peloton-Bike/dp/B000EXAMPL");
  await page.getByRole("button", { name: "Check it" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Recalled" })).toBeVisible();

  await page.getByRole("button", { name: "Check another product" }).click();
  await page.getByRole("tab", { name: "Scan barcode" }).click();
  await expect(page.getByRole("button", { name: "Scan with camera" })).toBeVisible();
  await page.getByLabel("Or type the barcode digits").fill("012345678905");
  await page.getByRole("button", { name: "Check it" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Recalled" })).toBeVisible();

  await page.getByRole("button", { name: "Check another product" }).click();
  await page.getByRole("tab", { name: "Vehicle VIN" }).click();
  await page.getByLabel("Vehicle identification number (VIN)").fill("1hgcm82633a004352");
  await page.getByRole("button", { name: "Check it" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Recalled" })).toBeVisible();

  expect(api.checks.map((c) => (c as { input: { type: string } }).input)).toEqual([
    { type: "link", value: "https://www.amazon.com/Peloton-Bike/dp/B000EXAMPL" },
    { type: "barcode", value: "012345678905" },
    { type: "vin", value: "1HGCM82633A004352" },
  ]);
});

test("a rate-limited check explains itself", async ({ page }) => {
  await page.route("**/v1/check", (route) =>
    route.fulfill({ status: 429, headers: { "Retry-After": "30" }, json: { detail: "slow" } }),
  );
  await page.goto("/check");
  await page.getByLabel("What is it?").fill("anything");
  await page.getByRole("button", { name: "Check it" }).click();
  // Scoped to main: Next.js adds its own role="alert" route announcer.
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(/Too many checks/);
});
