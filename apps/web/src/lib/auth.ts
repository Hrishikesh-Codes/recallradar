import "server-only";

import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { anonymous } from "better-auth/plugins/anonymous";
import { magicLink } from "better-auth/plugins/magic-link";

import { pool } from "@/lib/db";
import { sendSignInLink } from "@/lib/mail";

const timestamps = { createdAt: "created_at", updatedAt: "updated_at" } as const;

/**
 * Better Auth: email magic links only (no passwords), plus anonymous demo accounts. The tables
 * are created by the Python migrations (packages/core, revision 0005) with snake_case columns,
 * mapped here field by field.
 */
export const auth = betterAuth({
  appName: "RecallRadar",
  baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
  secret: process.env.BETTER_AUTH_SECRET,
  database: pool,
  telemetry: { enabled: false },
  user: {
    modelName: "auth_user",
    fields: { emailVerified: "email_verified", ...timestamps },
  },
  session: {
    modelName: "auth_session",
    fields: {
      expiresAt: "expires_at",
      ipAddress: "ip_address",
      userAgent: "user_agent",
      userId: "user_id",
      ...timestamps,
    },
    expiresIn: 60 * 60 * 24 * 30,
  },
  account: {
    modelName: "auth_account",
    fields: {
      accountId: "account_id",
      providerId: "provider_id",
      userId: "user_id",
      accessToken: "access_token",
      refreshToken: "refresh_token",
      idToken: "id_token",
      accessTokenExpiresAt: "access_token_expires_at",
      refreshTokenExpiresAt: "refresh_token_expires_at",
      ...timestamps,
    },
  },
  verification: {
    modelName: "auth_verification",
    fields: { expiresAt: "expires_at", ...timestamps },
  },
  advanced: {
    cookiePrefix: "recallradar",
    // We don't need users' IP addresses, so sessions don't record them.
    ipAddress: { disableIpTracking: true },
  },
  plugins: [
    magicLink({
      expiresIn: 60 * 15,
      storeToken: "hashed",
      sendMagicLink: async ({ email, url }) => sendSignInLink(email, url),
    }),
    anonymous({
      emailDomainName: "demo.recallradar.invalid",
      schema: { user: { fields: { isAnonymous: "is_anonymous" } } },
      // Signing in from a demo account keeps the demo list: move its items to the real account.
      onLinkAccount: async ({ anonymousUser, newUser }) => {
        await pool.query("UPDATE watch_item SET user_id = $1 WHERE user_id = $2", [
          newUser.user.id,
          anonymousUser.user.id,
        ]);
      },
    }),
    nextCookies(), // must be last: lets Server Actions set the session cookie
  ],
});

export type Session = typeof auth.$Infer.Session;
