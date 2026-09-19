import { routing } from "@/i18n/routing";

export const ACCESS_COOKIE = "jacrag_access";
export const REFRESH_COOKIE = "jacrag_refresh";
export const PUBLIC_PATHS = ["/login", "/register", "/onboarding"];

export type AppLocale = (typeof routing.locales)[number];

export function stripLocale(pathname: string): { locale: AppLocale; path: string } {
  const segments = pathname.split("/").filter(Boolean);
  const hasLocale = routing.locales.includes(segments[0] as AppLocale);
  const locale = hasLocale ? (segments[0] as AppLocale) : routing.defaultLocale;
  const rest = hasLocale ? segments.slice(1) : segments;
  return { locale, path: "/" + rest.join("/") };
}

export function isPublicPath(path: string): boolean {
  return PUBLIC_PATHS.some(
    (publicPath) => path === publicPath || path.startsWith(`${publicPath}/`),
  );
}

export function hasSessionCookie(
  get: (name: string) => { value: string } | undefined,
): boolean {
  return Boolean(get(ACCESS_COOKIE) ?? get(REFRESH_COOKIE));
}
