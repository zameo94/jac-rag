import { useEffect, useRef } from "react";

const parsedIdle = Number.parseInt(process.env.SESSION_IDLE_TIMEOUT_MINUTES ?? "", 10);
export const SESSION_IDLE_TIMEOUT_MS =
  Number.isFinite(parsedIdle) && parsedIdle > 0 ? parsedIdle * 60_000 : 0;

type Listener = () => void;
const listeners = new Set<Listener>();

/** Signals user activity (mouse/keyboard/API traffic) so idle watchers re-arm. */
export function touchSession(): void {
  for (const listener of listeners) {
    listener();
  }
}

export function onSessionActivity(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Logs the user out after `idleMs` without activity while `enabled`. */
export function useSessionIdle({
  enabled,
  idleMs = SESSION_IDLE_TIMEOUT_MS,
  onIdle,
}: {
  enabled: boolean;
  idleMs?: number;
  onIdle: () => void;
}): void {
  const onIdleRef = useRef(onIdle);
  useEffect(() => {
    onIdleRef.current = onIdle;
  }, [onIdle]);

  useEffect(() => {
    if (!enabled || idleMs <= 0) return;

    let timer: number | undefined;
    const schedule = (): void => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => onIdleRef.current(), idleMs);
    };

    const ACTIVITY_EVENTS = [
      "pointerdown",
      "pointermove",
      "keydown",
      "scroll",
      "touchstart",
      "click",
    ] as const;
    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, schedule, { passive: true });
    }
    const unsubscribe = onSessionActivity(schedule);

    schedule();

    return () => {
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, schedule);
      }
      unsubscribe();
      window.clearTimeout(timer);
    };
  }, [enabled, idleMs]);
}