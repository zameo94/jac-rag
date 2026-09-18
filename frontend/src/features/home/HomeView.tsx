"use client";

import { Navbar } from "@/components/Navbar";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { OptionsMenu } from "@/features/navigation/OptionsMenu";
import { TenantProvider } from "@/features/tenants/TenantProvider";

import { HomeContent } from "./HomeContent";

export function HomeView() {
  return (
    <RequireAuth>
      <TenantProvider>
        <div className="min-h-screen">
          <Navbar>
            <OptionsMenu />
          </Navbar>
          <HomeContent />
        </div>
      </TenantProvider>
    </RequireAuth>
  );
}
