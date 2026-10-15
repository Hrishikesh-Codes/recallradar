import type { CheckInput } from "@/lib/api/client";

/**
 * A check started elsewhere (the landing page's "Try it now") that /check should run on load.
 * Kept in sessionStorage rather than the URL, so product text never reaches server logs.
 */
const KEY = "recallradar:pending-check";
/** A "Save to my list" that had to wait for sign-in; /list saves it afterwards. */
const SAVE_KEY = "recallradar:pending-save";

function save(key: string, input: CheckInput): void {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(input));
  } catch {
    // Storage blocked (private mode): the next page just opens empty.
  }
}

export const savePendingCheck = (input: CheckInput) => save(KEY, input);
export const savePendingSave = (input: CheckInput) => save(SAVE_KEY, input);
export const takePendingCheck = () => take(KEY);
export const takePendingSave = () => take(SAVE_KEY);

function take(key: string): CheckInput | null {
  try {
    const raw = window.sessionStorage.getItem(key);
    window.sessionStorage.removeItem(key);
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    if (
      parsed &&
      typeof parsed === "object" &&
      "type" in parsed &&
      "value" in parsed &&
      ["text", "link", "barcode", "vin"].includes(String(parsed.type)) &&
      typeof parsed.value === "string"
    ) {
      return parsed as CheckInput;
    }
  } catch {
    // Storage blocked or malformed: start empty.
  }
  return null;
}
