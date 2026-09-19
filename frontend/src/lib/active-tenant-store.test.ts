import { afterEach, describe, expect, it } from "vitest";

import { activeTenantStore } from "@/lib/active-tenant-store";

afterEach(() => {
  activeTenantStore.clear();
});

describe("activeTenantStore", () => {
  it("stores and returns the active tenant", () => {
    activeTenantStore.set(42);

    expect(activeTenantStore.get()).toBe(42);
  });

  it("returns null when unset", () => {
    expect(activeTenantStore.get()).toBeNull();
  });

  it("clears the stored tenant", () => {
    activeTenantStore.set(42);

    activeTenantStore.clear();

    expect(activeTenantStore.get()).toBeNull();
  });

  it("returns null for a non-numeric value", () => {
    window.localStorage.setItem("jacrag_active_tenant", "not-a-number");

    expect(activeTenantStore.get()).toBeNull();
  });
});
