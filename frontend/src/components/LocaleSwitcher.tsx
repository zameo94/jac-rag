"use client";

import { useLocale } from "next-intl";

import { ItalyFlag, UnitedStatesFlag } from "@/components/flags";
import { usePathname, useRouter } from "@/i18n/navigation";
import type { AppLocale } from "@/i18n/routing";

const LOCALES: { code: AppLocale; label: string; Flag: typeof ItalyFlag }[] = [
  { code: "it", label: "Italiano", Flag: ItalyFlag },
  { code: "en", label: "English", Flag: UnitedStatesFlag },
];

export function LocaleSwitcher({ className = "" }: { className?: string }) {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  function switchLocale(nextLocale: AppLocale) {
    if (nextLocale === locale) return;
    router.replace(pathname, { locale: nextLocale });
  }

  return (
    <div
      role="group"
      aria-label="Language"
      className={`inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white p-1 ${className}`}
    >
      {LOCALES.map(({ code, label, Flag }) => {
        const active = code === locale;
        return (
          <button
            key={code}
            type="button"
            onClick={() => switchLocale(code)}
            aria-label={label}
            aria-pressed={active}
            title={label}
            className={`flex h-7 w-7 items-center justify-center rounded-full transition ${
              active ? "ring-2 ring-slate-900" : "opacity-60 hover:opacity-100"
            }`}
          >
            <Flag className="h-5 w-5 rounded-[3px]" />
          </button>
        );
      })}
    </div>
  );
}
