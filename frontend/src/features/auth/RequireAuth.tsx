"use client";

import { useEffect } from "react";

import { useRouter } from "@/i18n/navigation";

import { useAuth } from "./AuthProvider";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return <p className="p-8 text-slate-500">...</p>;
  }

  return <>{children}</>;
}
