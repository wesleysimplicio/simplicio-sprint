import type { RunEvent } from "./types";
import { getLocalRunEvents, isLocalFallbackUrl } from "./localFallback";

export type SubscribeOpts = {
  onEvent: (event: RunEvent) => void;
  onError?: (err: unknown) => void;
  onOpen?: () => void;
};

export type Subscription = { close: () => void };

/**
 * Subscribe to a backend Server-Sent Events stream.
 *
 * Web-only: uses the browser-native EventSource. The app moved to web-first
 * (no React Native runtime), so the previous react-native-event-source branch
 * is gone — every consumer runs in the browser at http://localhost:8081.
 */
export function subscribeToRun(url: string, opts: SubscribeOpts): Subscription {
  if (isLocalFallbackUrl(url)) {
    let closed = false;
    const timers = getLocalRunEvents(url).map((event, index) =>
      setTimeout(() => {
        if (!closed) opts.onEvent(event);
      }, 220 * (index + 1)),
    );
    opts.onOpen?.();
    return {
      close: () => {
        closed = true;
        timers.forEach(clearTimeout);
      },
    };
  }

  const ES = (globalThis as { EventSource?: typeof EventSource }).EventSource;
  if (!ES) {
    opts.onError?.(new Error("EventSource not available in this runtime"));
    return { close: () => undefined };
  }

  const es = new ES(url);
  es.onopen = () => opts.onOpen?.();
  es.onerror = (e) => opts.onError?.(e);
  es.onmessage = (e: MessageEvent<string>) => {
    try {
      opts.onEvent(JSON.parse(e.data) as RunEvent);
    } catch (err) {
      opts.onError?.(err);
    }
  };

  return { close: () => es.close() };
}
