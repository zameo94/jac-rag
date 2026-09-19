import { setRequestLocale } from "next-intl/server";

import { HomeView } from "@/features/home/HomeView";

export default async function IndexPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <HomeView />;
}
