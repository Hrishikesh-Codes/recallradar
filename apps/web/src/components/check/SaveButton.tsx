"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { saveItem } from "@/app/list/actions";
import { Button } from "@/components/ui/Button";
import type { CheckInput } from "@/lib/api/client";
import { savePendingSave } from "@/lib/pendingCheck";

/** Save the checked product to My List; signs in first if needed, then finishes the save. */
export function SaveButton({ input }: { input: CheckInput }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [state, setState] = useState<
    { kind: "idle" | "saved" } | { kind: "error"; message: string }
  >({
    kind: "idle",
  });

  if (state.kind === "saved") {
    return (
      <p role="status" className="self-center text-muted-1">
        Saved. We&apos;ll keep checking it.{" "}
        <Link href="/list" className="text-accent underline underline-offset-4">
          See my list
        </Link>
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <Button
        disabled={pending}
        onClick={() =>
          startTransition(async () => {
            const result = await saveItem(input);
            if (result.status === "saved") setState({ kind: "saved" });
            else if (result.status === "error")
              setState({ kind: "error", message: result.message });
            else {
              savePendingSave(input);
              router.push("/sign-in?next=/list");
            }
          })
        }
      >
        {pending ? "Saving…" : "Save to my list"}
      </Button>
      {state.kind === "error" ? (
        <p role="alert" className="text-caption text-accent">
          {state.message}
        </p>
      ) : null}
    </div>
  );
}
