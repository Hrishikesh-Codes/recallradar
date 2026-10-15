import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type CheckInput = Schemas["CheckInput"];
export type CheckResponse = Schemas["CheckResponse"];
export type MatchOut = Schemas["MatchOut"];
export type RecallSummary = Schemas["RecallSummary"];
export type QueryOut = Schemas["QueryOut"];
export type Coverage = Schemas["Coverage"];
export type Stats = Schemas["Stats"];
export type FeedbackLabel = Schemas["FeedbackRequest"]["label"];

/** The FastAPI service. Browsers call it directly (CORS); it holds no user secrets. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryAfterSeconds?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    // The free API host sleeps when idle; the first request after that can fail or be slow.
    throw new ApiError("We couldn't reach the recall service. Please try again.", 0);
  }
  if (!response.ok) {
    const retryAfter = Number(response.headers.get("Retry-After")) || undefined;
    let detail = "Something went wrong on our side. Please try again.";
    if (response.status === 429) {
      detail = "Too many checks from your network. Please wait a moment and try again.";
    } else if (response.status === 422) {
      detail = "We couldn't read that. Check the input and try again.";
    }
    throw new ApiError(detail, response.status, retryAfter);
  }
  return (await response.json()) as T;
}

export function checkProduct(
  input: CheckInput,
  options: { purchaseDate?: string; signal?: AbortSignal } = {},
): Promise<CheckResponse> {
  return request<CheckResponse>("/v1/check", {
    method: "POST",
    body: JSON.stringify({ input, purchase_date: options.purchaseDate ?? null }),
    signal: options.signal ?? null,
  });
}

export function sendFeedback(body: {
  check_id: string;
  recall_id: number;
  label: FeedbackLabel;
  tier_shown: CheckResponse["verdict"] | null;
  query: QueryOut;
}): Promise<unknown> {
  return request("/v1/feedback", { method: "POST", body: JSON.stringify(body) });
}

export type Identified = Schemas["Identified"];

/** How the API reads an input, without checking it (for previews before a check). */
export function identify(input: CheckInput, signal?: AbortSignal): Promise<Identified> {
  return request<Identified>("/v1/identify", {
    method: "POST",
    body: JSON.stringify({ input, purchase_date: null }),
    signal: signal ?? null,
  });
}
