import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const refreshTenants = vi.fn().mockResolvedValue(undefined);
const selectTenant = vi.fn();

const apiMock = vi.hoisted(() => ({ tenants: { create: vi.fn() } }));

vi.mock("next-intl", () => ({
  useLocale: () => "it",
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "tenants.name": "Name",
      "tenants.slug": "Identifier",
      "tenants.slugPlaceholder": "If empty, generated from the name",
      "tenants.defaultLocale": "Default language",
      "tenants.answerMode": "Answer mode",
      "tenants.strict": "Strict",
      "tenants.assistive": "Assistive",
      "tenants.createCta": "Create workspace",
    };
    return (key: string) => messages[`${namespace}.${key}`] ?? key;
  },
}));

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/features/tenants/TenantProvider", () => ({
  useTenant: () => ({ refreshTenants, selectTenant }),
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

import { CreateWorkspaceForm } from "@/features/workspaces/CreateWorkspaceForm";

beforeEach(() => {
  push.mockClear();
  refreshTenants.mockClear();
  selectTenant.mockClear();
  apiMock.tenants.create.mockReset();
  apiMock.tenants.create.mockResolvedValue({ id: 5, name: "Acme", slug: "acme" });
});

function submit() {
  fireEvent.submit(
    screen.getByRole("button", { name: "Create workspace" }).closest("form") as HTMLFormElement,
  );
}

describe("CreateWorkspaceForm", () => {
  it("shows the slug placeholder", () => {
    render(<CreateWorkspaceForm />);

    expect(
      screen.getByPlaceholderText("If empty, generated from the name"),
    ).toBeInTheDocument();
  });

  it("creates the workspace and selects it", async () => {
    render(<CreateWorkspaceForm />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Acme" } });
    submit();

    await waitFor(() =>
      expect(apiMock.tenants.create).toHaveBeenCalledWith("Acme", "", "it", "strict"),
    );
    await waitFor(() => expect(refreshTenants).toHaveBeenCalled());
    expect(selectTenant).toHaveBeenCalledWith(5);
    expect(push).toHaveBeenCalledWith("/");
  });

  it("sends the chosen answer mode", async () => {
    render(<CreateWorkspaceForm />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Acme" } });
    fireEvent.change(screen.getByLabelText("Answer mode"), {
      target: { value: "assistive" },
    });
    submit();

    await waitFor(() =>
      expect(apiMock.tenants.create).toHaveBeenCalledWith(
        "Acme",
        "",
        "it",
        "assistive",
      ),
    );
  });
});
