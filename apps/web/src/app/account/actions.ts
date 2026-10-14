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
