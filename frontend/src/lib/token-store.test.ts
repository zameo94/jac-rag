import { afterEach, describe, expect, it } from "vitest";

import { activeTenantStore, tokenStore } from "@/lib/token-store";

afterEach(() => {
  tokenStore.clear();
});

describe("tokenStore", () => {
  it("stores and returns tokens", () => {
    tokenStore.set("access", "refresh");

    expect(tokenStore.getAccess()).toBe("access");
    expect(tokenStore.getRefresh()).toBe("refresh");
  });

  it("clears tokens", () => {
    tokenStore.set("access", "refresh");

    tokenStore.clear();

    expect(tokenStore.getAccess()).toBeNull();
    expect(tokenStore.getRefresh()).toBeNull();
  });
});

describe("activeTenantStore", () => {
  it("stores and returns the active tenant", () => {
    activeTenantStore.set(42);

    expect(activeTenantStore.get()).toBe(42);
  });

  it("returns null when unset", () => {
    expect(activeTenantStore.get()).toBeNull();
  });

  it("clears when tokens are cleared", () => {
    activeTenantStore.set(42);

    tokenStore.clear();

    expect(activeTenantStore.get()).toBeNull();
  });
});
