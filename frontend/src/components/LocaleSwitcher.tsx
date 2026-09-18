"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { ItalyFlag, UnitedStatesFlag } from "@/components/flags";
import { ChevronDownIcon } from "@/components/icons";
import { usePathname, useRouter } from "@/i18n/navigation";
import type { AppLocale } from "@/i18n/routing";

const LOCALES: { code: AppLocale; label: string; Flag: typeof ItalyFlag }[] = [
  { code: "it", label: "Italiano", Flag: ItalyFlag },
  { code: "en", label: "English", Flag: UnitedStatesFlag },
];

export function LocaleSwitcher({ className = "" }: { className?: string }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("common");
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const current = LOCALES.find((entry) => entry.code === locale) ?? LOCALES[0];

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  function select(nextLocale: AppLocale) {
    setOpen(false);
    if (nextLocale === locale) return;
    router.replace(pathname, { locale: nextLocale });
  }

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("language")}
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2 rounded border border-slate-300 bg-white px-2 py-1 text-sm"
      >
        <current.Flag className="h-4 w-5 rounded-[2px]" />
        <span className="uppercase">{current.code}</span>
        <ChevronDownIcon className="h-4 w-4 text-slate-500" />
      </button>

      {open && (
        <ul
          role="menu"
          className="absolute right-0 z-20 mt-1 w-40 overflow-hidden rounded border border-slate-200 bg-white py-1 shadow-lg"
        >
          {LOCALES.map(({ code, label, Flag }) => (
            <li key={code}>
              <button
                type="button"
                role="menuitem"
                aria-current={code === locale}
                onClick={() => select(code)}
                className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-slate-50 ${
                  code === locale ? "font-medium" : ""
                }`}
              >
                <Flag className="h-4 w-5 rounded-[2px]" />
                {label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
