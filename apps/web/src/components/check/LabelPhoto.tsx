"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { identify, type CheckInput, type Identified } from "@/lib/api/client";

const MAX_SIDE = 1600; // enough for label text, small enough to read quickly on a phone

type Stage =
  | { kind: "idle" }
  | { kind: "reading"; progress: number }
  | { kind: "read" }
  | { kind: "error"; message: string };

/** Shrink big phone photos before OCR: faster, and accuracy doesn't need 12 megapixels. */
async function downscale(file: File): Promise<HTMLCanvasElement> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return canvas;
}

/**
 * Photo of a label: text is read on this device (Tesseract.js, served from our own site), shown
 * for correction, and only the text is sent. The photo never leaves the device.
 */
export function LabelPhoto({
  onSubmit,
  disabled = false,
  submitLabel,
}: {
  onSubmit: (input: CheckInput) => void;
  disabled?: boolean;
  submitLabel: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [stage, setStage] = useState<Stage>({ kind: "idle" });
  const [preview, setPreview] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [found, setFound] = useState<Identified | null>(null);

  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview]);

  // Preview what we'd check as the text is corrected (debounced).
  useEffect(() => {
    if (!text.trim()) return;
    const abort = new AbortController();
    const timer = window.setTimeout(() => {
      identify({ type: "label", value: text.slice(0, 2000) }, abort.signal)
        .then(setFound)
        .catch(() => setFound(null));
    }, 500);
    return () => {
      window.clearTimeout(timer);
      abort.abort();
    };
  }, [text]);

  async function read(file: File) {
    setPreview(URL.createObjectURL(file));
    setStage({ kind: "reading", progress: 0 });
    setFound(null);
    try {
      const [{ createWorker }, image] = await Promise.all([
        import("tesseract.js"),
        downscale(file),
      ]);
      const worker = await createWorker("eng", 1, {
        workerPath: "/ocr/worker.min.js",
        corePath: "/ocr/core",
        langPath: "/ocr/lang",
        logger: (message) => {
          if (message.status === "recognizing text") {
            setStage({ kind: "reading", progress: Math.round(message.progress * 100) });
          }
        },
      });
      const { data } = await worker.recognize(image);
      await worker.terminate();
      const lines = data.text
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      setText(lines.join("\n"));
      setStage(
        lines.length
          ? { kind: "read" }
          : { kind: "error", message: "We couldn't read any text. Try a closer, sharper photo." },
      );
    } catch {
      setStage({ kind: "error", message: "We couldn't read this photo. Try another one." });
    }
  }

  const query = found?.query;
  const facts: Array<[string, string]> = [];
  if (query?.product_name) facts.push(["Product", query.product_name]);
  if (query?.model_numbers.length) facts.push(["Model", query.model_numbers.join(", ")]);
  if (query?.lot_codes.length) facts.push(["Lot", query.lot_codes.join(", ")]);
  if (query?.upcs.length)
    facts.push(["Barcode", query.upcs.map((u) => u.replace(/^0+/, "")).join(", ")]);

  return (
    <div className="flex flex-col gap-5">
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        aria-label="Photo of the product label"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void read(file);
          event.target.value = "";
        }}
      />
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant={stage.kind === "read" ? "outline" : "primary"}
          onClick={() => input.current?.click()}
          disabled={stage.kind === "reading"}
        >
          {preview ? "Use another photo" : "Take or choose a photo"}
        </Button>
        <p className="text-caption text-muted-2">
          The model sticker or label works best. Your photo stays on this device.
        </p>
      </div>

      {preview ? (
        // A local preview of the user's own photo (object URL), never uploaded.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={preview}
          alt="Your label photo"
          className="max-h-64 self-start rounded-sm object-contain"
        />
      ) : null}

      {stage.kind === "reading" ? (
        <p role="status" className="text-muted-1">
          Reading the label… {stage.progress}%
        </p>
      ) : null}
      {stage.kind === "error" ? (
        <p role="alert" className="text-accent">
          {stage.message}
        </p>
      ) : null}

      {stage.kind === "read" ? (
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (text.trim()) onSubmit({ type: "label", value: text.slice(0, 2000) });
          }}
        >
          <label className="flex flex-col gap-2">
            <span className="eyebrow text-muted-1">What we read</span>
            <textarea
              className="field min-h-36 font-mono text-caption"
              value={text}
              onChange={(event) => setText(event.target.value)}
              spellCheck={false}
            />
            <span className="text-caption text-muted-2">Fix anything we misread, then check.</span>
          </label>
          {facts.length ? (
            <dl
              className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-muted-1"
              aria-live="polite"
            >
              {facts.map(([label, value]) => (
                <div key={label} className="contents">
                  <dt className="eyebrow pt-1 text-muted-2">{label}</dt>
                  <dd className="break-words">{value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          <Button
            type="submit"
            variant="primary"
            className="self-start"
            disabled={disabled || !text.trim()}
          >
            {submitLabel}
          </Button>
        </form>
      ) : null}
    </div>
  );
}
