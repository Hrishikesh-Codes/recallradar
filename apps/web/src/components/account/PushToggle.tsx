"use client";

import { useEffect, useState } from "react";

import { removePush, savePush } from "@/app/account/actions";
import { Button } from "@/components/ui/Button";

const VAPID_PUBLIC_KEY = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY ?? "";

function keyBytes(base64: string): Uint8Array<ArrayBuffer> {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = window.atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

type State =
  | { kind: "loading" }
  | { kind: "unsupported"; reason: string }
  | { kind: "off" }
  | { kind: "on"; endpoint: string }
  | { kind: "error"; message: string };

/** Push notifications on this device, alongside email. */
export function PushToggle() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const supported = "serviceWorker" in navigator && "PushManager" in window && VAPID_PUBLIC_KEY;
    const standalone = window.matchMedia("(display-mode: standalone)").matches;
    const ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
    let cancelled = false;
    (async () => {
      if (!supported) {
        const reason =
          ios && !standalone
            ? "On iPhone and iPad, add RecallRadar to your Home Screen first (Share → Add to Home Screen), then open it from there."
            : "This browser doesn't support push notifications.";
        if (!cancelled) setState({ kind: "unsupported", reason });
        return;
      }
      const registration = await navigator.serviceWorker.getRegistration();
      const subscription = await registration?.pushManager.getSubscription();
      if (!cancelled) {
        setState(subscription ? { kind: "on", endpoint: subscription.endpoint } : { kind: "off" });
      }
    })().catch(() => !cancelled && setState({ kind: "off" }));
    return () => {
      cancelled = true;
    };
  }, []);

  async function turnOn() {
    setState({ kind: "loading" });
    try {
      const registration =
        (await navigator.serviceWorker.getRegistration()) ??
        (await navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }));
      await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyBytes(VAPID_PUBLIC_KEY),
      });
      const saved = await savePush(JSON.parse(JSON.stringify(subscription)));
      if (!saved.ok) {
        await subscription.unsubscribe();
        setState({ kind: "error", message: saved.message ?? "We couldn't turn push on." });
        return;
      }
      setState({ kind: "on", endpoint: subscription.endpoint });
    } catch {
      setState({
        kind: "error",
        message:
          Notification.permission === "denied"
            ? "Notifications are blocked for this site in your browser settings."
            : "We couldn't turn push on. Try again.",
      });
    }
  }

  async function turnOff(endpoint: string) {
    setState({ kind: "loading" });
    const registration = await navigator.serviceWorker.getRegistration();
    await (await registration?.pushManager.getSubscription())?.unsubscribe();
    await removePush(endpoint);
    setState({ kind: "off" });
  }

  if (state.kind === "loading")
    return <p className="text-caption text-muted-2">Checking this device…</p>;
  if (state.kind === "unsupported")
    return <p className="text-caption text-muted-1">{state.reason}</p>;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-muted-1">
        {state.kind === "on"
          ? "Push notifications are on for this device."
          : "Get a notification on this device when a recall matches your list."}
      </p>
      {state.kind === "on" ? (
        <Button arrow={false} className="self-start" onClick={() => void turnOff(state.endpoint)}>
          Turn off on this device
        </Button>
      ) : (
        <Button className="self-start" onClick={() => void turnOn()}>
          Turn on push notifications
        </Button>
      )}
      {state.kind === "error" ? (
        <p role="alert" className="text-caption text-accent">
          {state.message}
        </p>
      ) : null}
    </div>
  );
}
