"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { refresh } from "next/cache";

import { ApiError } from "@/lib/api/client";
import { getViewer, parseCheckInput, userFetch, type Item } from "@/lib/api/server";
import { auth } from "@/lib/auth";

export type SaveResult =
  { status: "saved"; item: Item } | { status: "sign_in" } | { status: "error"; message: string };

/** Save a product to the signed-in user's list. Returns "sign_in" when nobody is signed in. */
export async function saveItem(input: unknown, label?: unknown): Promise<SaveResult> {
  const checked = parseCheckInput(input);
  if (!checked) return { status: "error", message: "We couldn't read that product." };
  const viewer = await getViewer();
  if (!viewer) return { status: "sign_in" };
  try {
    const item = await userFetch<Item>(viewer.id, "/v1/me/items", {
      method: "POST",
      body: JSON.stringify({
        input: checked,
        label: typeof label === "string" && label.trim() ? label.trim().slice(0, 200) : null,
      }),
    });
    refresh();
    return { status: "saved", item };
  } catch (error) {
    return {
      status: "error",
      message: error instanceof ApiError ? error.message : "We couldn't save it. Try again.",
    };
  }
}

async function requireViewer() {
  const viewer = await getViewer();
  if (!viewer) redirect("/sign-in?next=/list");
  return viewer;
}

export async function removeItem(itemId: number): Promise<void> {
  const viewer = await requireViewer();
  if (!Number.isSafeInteger(itemId)) return;
  await userFetch(viewer.id, `/v1/me/items/${itemId}`, { method: "DELETE" });
  refresh();
}

/** "Not my product" (or undo it) for one recall on one item. */
export async function setDismissed(itemId: number, recallId: number, dismissed: boolean) {
  const viewer = await requireViewer();
  if (!Number.isSafeInteger(itemId) || !Number.isSafeInteger(recallId)) return;
  const action = dismissed ? "dismiss" : "restore";
  await userFetch(viewer.id, `/v1/me/items/${itemId}/matches/${recallId}/${action}`, {
    method: "POST",
  });
  refresh();
}

/** "Try the demo": a private, temporary account with a list of real examples. */
export async function startDemo(): Promise<void> {
  const viewer = await getViewer();
  if (viewer) {
    // Already signed in: a real account keeps its own list.
    if (viewer.isAnonymous) await userFetch(viewer.id, "/v1/me/demo", { method: "POST" });
    redirect("/list");
  }
  // The new session cookie goes out with this response, so the request's own cookies can't
  // tell us who signed in; the sign-in result does.
  const signedIn = await auth.api.signInAnonymous({ headers: await headers() });
  if (!signedIn) redirect("/sign-in");
  await userFetch(signedIn.user.id, "/v1/me/demo", { method: "POST" });
  redirect("/list");
}
