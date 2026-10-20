"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { CheckForm, EXAMPLES } from "@/components/check/CheckForm";
import { Checking } from "@/components/check/Checking";
import { VerdictView } from "@/components/check/VerdictView";
import { cn } from "@/lib/cn";
import { ApiError, checkProduct, type CheckInput, type CheckResponse } from "@/lib/api/client";
import { takePendingCheck } from "@/lib/pendingCheck";

type State =
  | { kind: "idle" }
  | { kind: "checking"; input: CheckInput }
  | { kind: "done"; input: CheckInput; result: CheckResponse }
  | { kind: "error"; input: CheckInput; message: string };

export function CheckExperience({ recalls }: { recalls?: number }) {
  const [state, setState] = useState<State>({ kind: "idle" });
  const controller = useRef<AbortController | null>(null);
  const heading = useRef<HTMLDivElement>(null);

  const run = useCallback(async (input: CheckInput) => {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setState({ kind: "checking", input });
    try {
      const result = await checkProduct(input, { signal: abort.signal });
      setState({ kind: "done", input, result });
    } catch (error) {
      if (abort.signal.aborted) return;
      const message =
        error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
      setState({ kind: "error", input, message });
    }
  }, []);

  // Read once per mount; a ref survives React's development double-run of effects.
  const pendingRef = useRef<CheckInput | null | undefined>(undefined);
  useEffect(() => {
    if (pendingRef.current === undefined) pendingRef.current = takePendingCheck();
    const pending = pendingRef.current;
    // Start after this render commits, so the check runs like a click rather than mid-effect.
    const timer = pending
      ? window.setTimeout(() => {
          pendingRef.current = null;
          void run(pending);
        }, 0)
      : undefined;
    return () => {
      window.clearTimeout(timer);
      controller.current?.abort();
    };
  }, [run]);

  // Move focus to the result so screen readers and keyboard users land on the verdict.
  useEffect(() => {
    if (state.kind === "done" || state.kind === "error") heading.current?.focus();
    if (state.kind !== "checking") window.scrollTo({ top: 0 });
  }, [state.kind]);

  // The form rises in only when coming back to it, not on first load (axe measures contrast
  // straight away, and a fading form reads as low contrast).
  const [returned, setReturned] = useState(false);
  const reset = () => {
    setReturned(true);
    setState({ kind: "idle" });
  };

  return (
    <div ref={heading} tabIndex={-1} className="outline-none">
      {/* Each state rises into place as it appears (CSS, .rise-in). */}
      {state.kind === "checking" ? (
        <div className="rise-in">
          <Checking recalls={recalls} />
        </div>
      ) : null}
      {state.kind === "done" ? (
        <div className="rise-in">
          <VerdictView result={state.result} input={state.input} onCheckAnother={reset} />
        </div>
      ) : null}
      {state.kind === "idle" || state.kind === "error" ? (
        <div className={cn("flex flex-col gap-12", returned && "rise-in")}>
          {state.kind === "error" ? (
            <p role="alert" className="max-w-prose text-accent">
              {state.message}
            </p>
          ) : null}
          <CheckForm onSubmit={(input) => void run(input)} />
          <div className="flex flex-col gap-3">
            <p className="eyebrow text-muted-2">Or try a real example</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((example) => (
                <button
                  key={example.label}
                  type="button"
                  onClick={() => void run(example.input)}
                  className="chip cursor-pointer px-3 py-2.5 text-muted-1 transition-colors hover:text-text"
                >
                  {example.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
