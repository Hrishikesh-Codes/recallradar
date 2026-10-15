"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { refresh } from "next/cache";

import { getViewer, userFetch } from "@/lib/api/server";
import { auth } from "@/lib/auth";

export async function updateAlerts(formData: FormData): Promise<void> {
  const viewer = await getViewer();
  if (!viewer) redirect("/sign-in?next=/account");
  const tiers = formData.getAll("tier").filter((t) => t === "recalled" || t === "check_unit");
  await userFetch(viewer.id, "/v1/me/settings", {
    method: "PUT",
    body: JSON.stringify({
      email_alerts: formData.get("email_alerts") === "on",
      alert_tiers: tiers,
    }),
  });
  refresh();
}

export async function signOut(): Promise<void> {
  await auth.api.signOut({ headers: await headers() });
  redirect("/");
}

/** Deletes the account and everything derived from it (SPEC §2.9), then signs out. */
export async function deleteAccount(formData: FormData): Promise<void> {
  const viewer = await getViewer();
  if (!viewer) redirect("/");
  if (formData.get("confirm") !== "delete") redirect("/account?error=confirm");
  await userFetch(viewer.id, "/v1/me", { method: "DELETE" });
  // The session row is gone with the user; this clears the cookie.
  await auth.api.signOut({ headers: await headers() }).catch(() => undefined);
  redirect("/?deleted=1");
}

type PushJson = { endpoint?: unknown; keys?: { p256dh?: unknown; auth?: unknown } };

/** Store this browser's push subscription for the signed-in user. */
export async function savePush(subscription: unknown): Promise<{ ok: boolean; message?: string }> {
  const viewer = await getViewer();
  if (!viewer || viewer.isAnonymous)
    return { ok: false, message: "Sign in with your email first." };
  const { endpoint, keys } = (subscription ?? {}) as PushJson;
  if (
    typeof endpoint !== "string" ||
    !endpoint.startsWith("https://") ||
    typeof keys?.p256dh !== "string" ||
    typeof keys.auth !== "string"
  ) {
    return { ok: false, message: "This browser returned an unusable subscription." };
  }
  await userFetch(viewer.id, "/v1/me/push", {
    method: "PUT",
    body: JSON.stringify({ endpoint, keys: { p256dh: keys.p256dh, auth: keys.auth } }),
  });
  return { ok: true };
}

export async function removePush(endpoint: unknown): Promise<void> {
  const viewer = await getViewer();
  if (!viewer || typeof endpoint !== "string") return;
  await userFetch(viewer.id, "/v1/me/push/remove", {
    method: "POST",
    body: JSON.stringify({ endpoint }),
  });
}
