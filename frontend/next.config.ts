import path from "node:path";

import { config as loadEnv } from "dotenv";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const { parsed } = loadEnv({
  path: path.resolve(process.cwd(), "../.env"),
  processEnv: {},
});

for (const [key, value] of Object.entries(parsed ?? {})) {
  if (key.startsWith("NEXT_PUBLIC_") && process.env[key] === undefined) {
    process.env[key] = value;
  }
}

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default withNextIntl(nextConfig);
