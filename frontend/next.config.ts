import path from "node:path";

import { config as loadEnv } from "dotenv";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const { parsed } = loadEnv({
  path: path.resolve(process.cwd(), "../.env"),
  processEnv: {},
});

for (const [key, value] of Object.entries(parsed ?? {})) {
  if (
    (key.startsWith("NEXT_PUBLIC_") ||
      key === "API_PROXY_TARGET" ||
      key === "SESSION_IDLE_TIMEOUT_MINUTES") &&
    process.env[key] === undefined
  ) {
    process.env[key] = value;
  }
}

const apiProxyTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";
const sessionIdleTimeoutMinutes = Number.parseInt(
  process.env.SESSION_IDLE_TIMEOUT_MINUTES ?? "60",
  10,
);

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    SESSION_IDLE_TIMEOUT_MINUTES: String(
      Number.isFinite(sessionIdleTimeoutMinutes) && sessionIdleTimeoutMinutes > 0
        ? sessionIdleTimeoutMinutes
        : 0,
    ),
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/api/:path*`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
