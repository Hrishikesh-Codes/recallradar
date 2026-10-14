"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { savePendingCheck } from "@/lib/pendingCheck";

/** "Try it now" on the landing page: hands the input to /check, which runs it. */
export function TryIt() {
  const router = useRouter();
  const [value, setValue] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const text = value.trim();
    if (!text) return;
    const type = /^https?:\/\//i.test(text)
      ? "link"
      : /^\d[\d ]{6,16}$/.test(text)
        ? "barcode"
        : "text";
    savePendingCheck({ type, value: text });
    router.push("/check");
  }

  return (
    <form onSubmit={submit} className="flex w-full max-w-xl flex-col gap-3 sm:flex-row">
      <label htmlFor="try-it" className="sr-only">
        Product, link, or barcode digits
      </label>
      <input
        id="try-it"
        className="field flex-1"
        placeholder="Try it: a product, a link, or barcode digits"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        maxLength={2000}
        autoComplete="off"
      />
      <Button type="submit" variant="primary" disabled={!value.trim()}>
        Check
      </Button>
    </form>
  );
}
