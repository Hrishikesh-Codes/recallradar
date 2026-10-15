"use client";

import { useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { BarcodeScanner } from "@/components/check/BarcodeScanner";
import { LabelPhoto } from "@/components/check/LabelPhoto";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import type { CheckInput } from "@/lib/api/client";
import { cn } from "@/lib/cn";

type Mode = CheckInput["type"];

const MODES: ReadonlyArray<{ mode: Mode; label: string }> = [
  { mode: "text", label: "Describe it" },
  { mode: "link", label: "Paste a link" },
  { mode: "barcode", label: "Scan barcode" },
  { mode: "label", label: "Photo of label" },
  { mode: "vin", label: "Vehicle VIN" },
];

/** Real products from the evaluation set, one per verdict, so the demo shows every outcome. */
export const EXAMPLES: ReadonlyArray<{ label: string; input: CheckInput }> = [
  { label: "Peloton bike PL01", input: { type: "text", value: "Peloton bike PL01" } },
  {
    label: "Anker PowerCore 10000 A1263",
    input: { type: "text", value: "Anker PowerCore 10000 power bank A1263" },
  },
  { label: "Hydro Flask bottle", input: { type: "text", value: "Hydro Flask 32 oz water bottle" } },
  { label: "2019 Honda Civic", input: { type: "text", value: "2019 Honda Civic" } },
];

export function CheckForm({
  onSubmit,
  disabled = false,
  initialMode = "text",
  submitLabel = "Check it",
}: {
  onSubmit: (input: CheckInput) => void;
  disabled?: boolean;
  initialMode?: Mode;
  submitLabel?: string;
}) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [values, setValues] = useState<Record<Mode, string>>({
    text: "",
    link: "",
    barcode: "",
    vin: "",
    label: "",
  });
  const tabs = useRef<Array<HTMLButtonElement | null>>([]);
  const baseId = useId();

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = values[mode].trim();
    if (value) onSubmit({ type: mode, value });
  }

  function onTabKey(event: KeyboardEvent, index: number) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (index + step + MODES.length) % MODES.length;
    setMode(MODES[next]!.mode);
    tabs.current[next]?.focus();
  }

  const set = (value: string) => setValues((current) => ({ ...current, [mode]: value }));

  return (
    <div className="flex flex-col gap-6">
      <div role="tablist" aria-label="How to add the product" className="flex flex-wrap gap-2">
        {MODES.map((item, index) => (
          <button
            key={item.mode}
            ref={(element) => {
              tabs.current[index] = element;
            }}
            type="button"
            role="tab"
            id={`${baseId}-tab-${item.mode}`}
            aria-selected={mode === item.mode}
            aria-controls={`${baseId}-panel`}
            tabIndex={mode === item.mode ? 0 : -1}
            onClick={() => setMode(item.mode)}
            onKeyDown={(event) => onTabKey(event, index)}
            className={cn(
              "chip cursor-pointer px-3 py-2.5 transition-colors",
              mode === item.mode ? "bg-text text-bg-0" : "text-muted-1 hover:text-text",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`${baseId}-panel`}
        aria-labelledby={`${baseId}-tab-${mode}`}
        className="flex flex-col gap-6"
      >
        {mode === "barcode" ? (
          <BarcodeScanner
            onDetected={(code) => {
              set(code);
              onSubmit({ type: "barcode", value: code });
            }}
          />
        ) : null}
        {mode === "label" ? (
          <LabelPhoto onSubmit={onSubmit} disabled={disabled} submitLabel={submitLabel} />
        ) : null}
        <form onSubmit={submit} className={mode === "label" ? "hidden" : "flex flex-col gap-4"}>
          {mode === "text" ? (
            <TextField
              label="What is it?"
              hint="Brand and product, plus a model number if you have it."
              placeholder="e.g. Graco high chair, model 2074619"
              value={values.text}
              onChange={(event) => set(event.target.value)}
              maxLength={300}
              autoComplete="off"
            />
          ) : null}
          {mode === "link" ? (
            <TextField
              label="Product link"
              hint="We read the product name in the link itself. We never open store pages."
              placeholder="https://www.amazon.com/…"
              type="url"
              inputMode="url"
              value={values.link}
              onChange={(event) => set(event.target.value)}
              maxLength={2000}
              autoComplete="off"
            />
          ) : null}
          {mode === "barcode" ? (
            <TextField
              label="Or type the barcode digits"
              hint="The 8–14 digits printed under the bars."
              placeholder="e.g. 012345678905"
              inputMode="numeric"
              pattern="[0-9 ]{8,17}"
              value={values.barcode}
              onChange={(event) => set(event.target.value)}
              maxLength={17}
              autoComplete="off"
            />
          ) : null}
          {mode === "vin" ? (
            <TextField
              label="Vehicle identification number (VIN)"
              hint="17 characters, on the lower left of the windshield or on your registration. NHTSA decodes it; we don't keep it."
              placeholder="e.g. 1HGCM82633A004352"
              value={values.vin}
              onChange={(event) => set(event.target.value.toUpperCase())}
              maxLength={20}
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
            />
          ) : null}
          <Button
            type="submit"
            variant="primary"
            disabled={disabled || !values[mode].trim()}
            className="self-start"
          >
            {submitLabel}
          </Button>
        </form>
      </div>
    </div>
  );
}
