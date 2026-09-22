import { act, render } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { onSessionActivity, touchSession, useSessionIdle } from "@/lib/session-idle";

function Harness({
  enabled,
  idleMs,
  onIdle,
}: {
  enabled: boolean;
  idleMs: number;
  onIdle: () => void;
}) {
  useSessionIdle({ enabled, idleMs, onIdle });
  return null;
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("session activity store", () => {
  it("notifies listeners on touchSession", () => {
    const listener = vi.fn();
    onSessionActivity(listener);

    touchSession();

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("unsubscribes a listener", () => {
    const listener = vi.fn();
    const unsubscribe = onSessionActivity(listener);

    unsubscribe();
    touchSession();

    expect(listener).not.toHaveBeenCalled();
  });
});

describe("useSessionIdle", () => {
  it("fires onIdle after the idle window", () => {
    const onIdle = vi.fn();
    render(<Harness enabled idleMs={1000} onIdle={onIdle} />);

    act(() => vi.advanceTimersByTime(999));
    expect(onIdle).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(1));
    expect(onIdle).toHaveBeenCalledTimes(1);
  });

  it("re-arms the timer on user activity", () => {
    const onIdle = vi.fn();
    render(<Harness enabled idleMs={1000} onIdle={onIdle} />);

    act(() => vi.advanceTimersByTime(900));
    act(() => window.dispatchEvent(new Event("pointerdown")));
    act(() => vi.advanceTimersByTime(900));
    expect(onIdle).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(100));
    expect(onIdle).toHaveBeenCalledTimes(1);
  });

  it("re-arms the timer on API activity", () => {
    const onIdle = vi.fn();
    render(<Harness enabled idleMs={1000} onIdle={onIdle} />);

    act(() => vi.advanceTimersByTime(900));
    act(() => touchSession());
    act(() => vi.advanceTimersByTime(900));
    expect(onIdle).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(100));
    expect(onIdle).toHaveBeenCalledTimes(1);
  });

  it("does nothing while disabled", () => {
    const onIdle = vi.fn();
    render(<Harness enabled={false} idleMs={1000} onIdle={onIdle} />);

    act(() => vi.advanceTimersByTime(5000));

    expect(onIdle).not.toHaveBeenCalled();
  });

  it("uses the latest onIdle callback", () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = render(<Harness enabled idleMs={1000} onIdle={first} />);

    rerender(<Harness enabled idleMs={1000} onIdle={second} />);
    act(() => vi.advanceTimersByTime(1000));

    expect(second).toHaveBeenCalledTimes(1);
    expect(first).not.toHaveBeenCalled();
  });
});