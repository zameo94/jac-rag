"use client";

import { OnboardingPanel } from "@/features/onboarding/OnboardingPanel";
import { TenantProvider } from "@/features/tenants/TenantProvider";

export default function OnboardingPage() {
  return (
    <TenantProvider>
      <main className="mx-auto max-w-3xl px-4 py-16">
        <OnboardingPanel />
      </main>
    </TenantProvider>
  );
}
