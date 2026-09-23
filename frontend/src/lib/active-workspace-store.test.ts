import { afterEach, describe, expect, it } from "vitest";

import { activeWorkspaceStore } from "@/lib/active-workspace-store";

afterEach(() => {
  activeWorkspaceStore.clear();
});

describe("activeWorkspaceStore", () => {
  it("stores and returns the active workspace", () => {
    activeWorkspaceStore.set(42);

    expect(activeWorkspaceStore.get()).toBe(42);
  });

  it("returns null when unset", () => {
    expect(activeWorkspaceStore.get()).toBeNull();
  });

  it("clears the stored workspace", () => {
    activeWorkspaceStore.set(42);

    activeWorkspaceStore.clear();

    expect(activeWorkspaceStore.get()).toBeNull();
  });

  it("returns null for a non-numeric value", () => {
    window.localStorage.setItem("jacrag_active_workspace", "not-a-number");

    expect(activeWorkspaceStore.get()).toBeNull();
  });
});
