import { setRequestLocale } from "next-intl/server";

import { redirect } from "@/i18n/navigation";

export default async function IndexPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  redirect({ href: "/dashboard", locale });
}
