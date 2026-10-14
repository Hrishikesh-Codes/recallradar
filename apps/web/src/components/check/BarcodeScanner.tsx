"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

/** Retail barcodes only: those are what recalls list. */
const FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e"] as const;
const SCAN_INTERVAL_MS = 150;

type Detector = { detect(source: HTMLVideoElement): Promise<Array<{ rawValue: string }>> };

/**
 * The browser's own BarcodeDetector where it exists (Chrome on Android, macOS), otherwise the
 * ZXing WebAssembly reader (Safari, Firefox). The .wasm is served from our origin.
 */
async function createDetector(): Promise<Detector> {
  const native = (globalThis as { BarcodeDetector?: BarcodeDetectorConstructor }).BarcodeDetector;
  if (native) {
    const supported = await native.getSupportedFormats();
    if (FORMATS.every((format) => supported.includes(format))) {
      return new native({ formats: [...FORMATS] });
    }
  }
  const { BarcodeDetector, prepareZXingModule } = await import("barcode-detector/ponyfill");
  prepareZXingModule({
    overrides: {
      locateFile: (path: string, prefix: string) =>
        path.endsWith(".wasm") ? `/wasm/${path}` : prefix + path,
    },
  });
  return new BarcodeDetector({ formats: [...FORMATS] });
}

type BarcodeDetectorConstructor = {
  new (options: { formats: string[] }): Detector;
  getSupportedFormats(): Promise<string[]>;
};

type Status = "idle" | "starting" | "scanning" | "denied" | "unavailable";

export function BarcodeScanner({ onDetected }: { onDetected: (code: string) => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);
  const [status, setStatus] = useState<Status>("idle");

  const stop = useCallback(() => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => stop, [stop]);

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("unavailable");
      return;
    }
    setStatus("starting");
    try {
      const [stream, detector] = await Promise.all([
        navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" } },
          audio: false,
        }),
        createDetector(),
      ]);
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) return stop();
      video.srcObject = stream;
      await video.play();
      setStatus("scanning");

      const scan = async () => {
        if (!streamRef.current) return;
        try {
          const [found] = await detector.detect(video);
          if (found?.rawValue && /^\d{8,14}$/.test(found.rawValue)) {
            stop();
            setStatus("idle");
            navigator.vibrate?.(30);
            onDetected(found.rawValue);
            return;
          }
        } catch {
          // A frame that can't be read yet (camera warming up); try the next one.
        }
        timerRef.current = window.setTimeout(scan, SCAN_INTERVAL_MS);
      };
      void scan();
    } catch (error) {
      stop();
      const denied = error instanceof DOMException && error.name === "NotAllowedError";
      setStatus(denied ? "denied" : "unavailable");
    }
  }

  const active = status === "starting" || status === "scanning";
  return (
    <div className="flex flex-col gap-4">
      <div
        className={cn(
          "relative aspect-[4/3] w-full overflow-clip rounded-md bg-bg-1 shadow-[inset_0_0_0_1px_var(--color-line)]",
          !active && "hidden",
        )}
      >
        <video
          ref={videoRef}
          className="size-full object-cover"
          playsInline
          muted
          aria-label="Camera preview"
        />
        <div aria-hidden className="scan-reticle" />
        <p className="eyebrow glass absolute bottom-3 left-3 px-3 py-2 text-muted-1" role="status">
          {status === "starting" ? "Starting camera…" : "Point at the barcode"}
        </p>
      </div>
      {active ? (
        <Button
          arrow={false}
          onClick={() => {
            stop();
            setStatus("idle");
          }}
        >
          Stop camera
        </Button>
      ) : (
        <Button variant="primary" onClick={() => void start()}>
          Scan with camera
        </Button>
      )}
      {status === "denied" ? (
        <p className="text-caption text-muted-1" role="alert">
          Camera access was blocked. Allow it in your browser settings, or type the digits under the
          barcode below.
        </p>
      ) : null}
      {status === "unavailable" ? (
        <p className="text-caption text-muted-1" role="alert">
          This browser can&apos;t use the camera here. Type the digits under the barcode below.
        </p>
      ) : null}
    </div>
  );
}
