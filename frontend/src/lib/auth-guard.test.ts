import { describe, expect, it } from "vitest";

import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  hasSessionCookie,
  isPublicPath,
  stripLocale,
} from "@/lib/auth-guard";

function cookiesFrom(entries: Record<string, string>) {
  return (name: string) =>
    name in entries ? { value: entries[name] } : undefined;
}

describe("stripLocale", () => {
  it("extracts the locale and the remaining path", () => {
    expect(stripLocale("/it/dashboard")).toEqual({ locale: "it", path: "/dashboard" });
    expect(stripLocale("/en/dashboard/members")).toEqual({
      locale: "en",
      path: "/dashboard/members",
    });
  });

  it("uses the default locale when the first segment is not a locale", () => {
    expect(stripLocale("/dashboard")).toEqual({ locale: "it", path: "/dashboard" });
  });

  it("maps the root path to the home path", () => {
    expect(stripLocale("/it")).toEqual({ locale: "it", path: "/" });
  });

  it("handles an unknown locale as a normal path", () => {
    expect(stripLocale("/fr/dashboard")).toEqual({ locale: "it", path: "/fr/dashboard" });
  });
});

describe("isPublicPath", () => {
  it("treats auth and onboarding paths as public", () => {
    expect(isPublicPath("/login")).toBe(true);
    expect(isPublicPath("/register")).toBe(true);
    expect(isPublicPath("/onboarding")).toBe(true);
  });

  it("treats nested public paths as public", () => {
    expect(isPublicPath("/login/reset")).toBe(true);
  });

  it("treats app paths as protected", () => {
    expect(isPublicPath("/")).toBe(false);
    expect(isPublicPath("/dashboard")).toBe(false);
    expect(isPublicPath("/dashboard/members")).toBe(false);
  });

  it("does not match a path that merely starts with a public name", () => {
    expect(isPublicPath("/login-page")).toBe(false);
  });
});

describe("hasSessionCookie", () => {
  it("is true when the access cookie is present", () => {
    expect(hasSessionCookie(cookiesFrom({ [ACCESS_COOKIE]: "token" }))).toBe(true);
  });

  it("is true when only the refresh cookie is present", () => {
    expect(hasSessionCookie(cookiesFrom({ [REFRESH_COOKIE]: "token" }))).toBe(true);
  });

  it("is false when no session cookie is present", () => {
    expect(hasSessionCookie(cookiesFrom({}))).toBe(false);
  });
});
