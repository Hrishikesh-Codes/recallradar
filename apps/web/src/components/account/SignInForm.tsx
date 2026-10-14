"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { authClient } from "@/lib/authClient";

type Status =
  | { kind: "idle" }
  | { kind: "sending" }
  | { kind: "sent"; email: string }
  | { kind: "error"; message: string };

/** Only same-site paths are allowed as the post-sign-in destination. */
function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/list";
}

export function SignInForm({ next }: { next: string | null }) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function submit(event: FormEvent) {
    event.preventDefault();
    setStatus({ kind: "sending" });
    const { error } = await authClient.signIn.magicLink({
      email: email.trim(),
      callbackURL: safeNext(next),
      errorCallbackURL: "/sign-in?error=link",
    });
    setStatus(
      error
        ? { kind: "error", message: error.message ?? "We couldn't send the link. Try again." }
        : { kind: "sent", email: email.trim() },
    );
  }

  if (status.kind === "sent") {
    return (
      <div role="status" className="flex flex-col gap-3">
        <p className="display text-heading">Check your email</p>
        <p className="max-w-prose text-muted-1">
          We sent a sign-in link to <strong className="text-text">{status.email}</strong>. It works
          once and expires in 15 minutes. You can close this tab.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <TextField
        label="Email"
        type="email"
        autoComplete="email"
        required
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        hint="We'll email you a link. No password."
      />
      {status.kind === "error" ? (
        <p role="alert" className="text-accent">
          {status.message}
        </p>
      ) : null}
      <Button
        type="submit"
        variant="primary"
        className="self-start"
        disabled={status.kind === "sending"}
      >
        {status.kind === "sending" ? "Sending…" : "Email me a link"}
      </Button>
    </form>
  );
}
