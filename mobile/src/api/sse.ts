import { Platform } from "react-native";
import type { RunEvent } from "./types";

export type SubscribeOpts = {
  onEvent: (event: RunEvent) => void;
  onError?: (err: unknown) => void;
  onOpen?: () => void;
};

export type Subscription = { close: () => void };

export function subscribeToRun(url: string, opts: SubscribeOpts): Subscription {
  // Web has a native EventSource; React Native does not — use the polyfill.
  if (Platform.OS === "web" && typeof globalThis !== "undefined" && (globalThis as any).EventSource) {
    const es = new (globalThis as any).EventSource(url);
    const handleMessage = (e: { data: string }) => {
      try {
        opts.onEvent(JSON.parse(e.data) as RunEvent);
      } catch (err) {
        opts.onError?.(err);
      }
    };
    es.onmessage = handleMessage;
    es.onerror = (e: unknown) => opts.onError?.(e);
    es.onopen = () => opts.onOpen?.();
    return { close: () => es.close() };
  }

  // Lazy-require so web bundles don't include the RN polyfill.
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const RNEventSource = require("react-native-event-source").default;
  const es = new RNEventSource(url);
  es.addEventListener?.("open", () => opts.onOpen?.());
  es.addEventListener?.("error", (e: unknown) => opts.onError?.(e));
  es.addEventListener?.("message", (e: { data: string }) => {
    try {
      opts.onEvent(JSON.parse(e.data) as RunEvent);
    } catch (err) {
      opts.onError?.(err);
    }
  });
  return {
    close: () => {
      es.removeAllListeners?.();
      es.close?.();
    },
  };
}
