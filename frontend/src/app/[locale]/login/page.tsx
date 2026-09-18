"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { useAuth } from "@/features/auth/AuthProvider";
import { Link } from "@/i18n/navigation";

export default function LoginPage() {
  const t = useTranslations("auth");
  const common = useTranslations("common");
  const locale = useLocale();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 px-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("loginTitle")}</h1>
        <LocaleSwitcher />
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          {common("email")}
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="rounded border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {common("password")}
          <input
            type="password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="rounded border border-slate-300 px-3 py-2"
          />
        </label>
        <ErrorMessage error={error} />
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {t("loginCta")}
        </button>
      </form>
      <p className="text-sm text-slate-600">
        {t("noAccount")}{" "}
        <Link href="/register" locale={locale} className="underline">
          {t("goRegister")}
        </Link>
      </p>
    </main>
  );
}
