import type { CheckInput } from "@/lib/api/client";

/**
 * A check started elsewhere (the landing page's "Try it now") that /check should run on load.
 * Kept in sessionStorage rather than the URL, so product text never reaches server logs.
 */
const KEY = "recallradar:pending-check";

export function savePendingCheck(input: CheckInput): void {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(input));
  } catch {
    // Storage blocked (private mode): /check opens empty instead.
  }
}

export function takePendingCheck(): CheckInput | null {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    window.sessionStorage.removeItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    if (
      parsed &&
      typeof parsed === "object" &&
      "type" in parsed &&
      "value" in parsed &&
      ["text", "link", "barcode"].includes(String(parsed.type)) &&
      typeof parsed.value === "string"
    ) {
      return parsed as CheckInput;
    }
  } catch {
    // Storage blocked or malformed: start empty.
  }
  return null;
}
