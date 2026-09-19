import createMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";

import { routing } from "./i18n/routing";
import { hasSessionCookie, isPublicPath, stripLocale } from "./lib/auth-guard";

const intlMiddleware = createMiddleware(routing);

export default function middleware(request: NextRequest) {
  const response = intlMiddleware(request);

  const { locale, path } = stripLocale(request.nextUrl.pathname);
  const hasSession = hasSessionCookie((name) => request.cookies.get(name));

  if (!hasSession && !isPublicPath(path)) {
    const url = request.nextUrl.clone();
    url.pathname = `/${locale}/login`;
    url.search = "";
    return NextResponse.redirect(url);
  }

  return response;
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
