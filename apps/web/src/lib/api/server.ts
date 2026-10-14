import "server-only";

import { SignJWT } from "jose";
import { headers } from "next/headers";

import { API_URL, ApiError, type CheckInput } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { auth } from "@/lib/auth";

export type Item = components["schemas"]["ItemOut"];
export type Me = components["schemas"]["Me"];
export type AccountSettings = components["schemas"]["SettingsOut"];

export type Viewer = { id: string; email: string | null; isAnonymous: boolean };

/** The signed-in user for this request, or null. Reads cookies: call it behind <Suspense>. */
export async function getViewer(): Promise<Viewer | null> {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return null;
  const isAnonymous = Boolean((session.user as { isAnonymous?: boolean | null }).isAnonymous);
  return { id: session.user.id, email: isAnonymous ? null : session.user.email, isAnonymous };
}

function apiSecret(): Uint8Array {
  const secret = process.env.API_TOKEN_SECRET;
  if (!secret || secret.length < 32) throw new Error("API_TOKEN_SECRET is not set");
  return new TextEncoder().encode(secret);
}

/**
 * Call the API as `userId`. The token lives for two minutes and never reaches the browser:
 * only this server holds API_TOKEN_SECRET (see apps/api/src/recallradar_api/auth.py).
 */
export async function userFetch<T>(
  userId: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = await new SignJWT({})
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(userId)
    .setIssuer("recallradar-web")
    .setAudience("recallradar-api")
    .setIssuedAt()
    .setExpirationTime("2m")
    .sign(apiSecret());
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : "Something went wrong.";
    throw new ApiError(detail, response.status);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

/** Server Action inputs come from the network: check them before use. */
export function parseCheckInput(value: unknown): CheckInput | null {
  if (!value || typeof value !== "object") return null;
  const { type, value: text } = value as { type?: unknown; value?: unknown };
  if (type !== "text" && type !== "link" && type !== "barcode") return null;
  if (typeof text !== "string" || !text.trim() || text.length > 2000) return null;
  return { type, value: text.trim() };
}
