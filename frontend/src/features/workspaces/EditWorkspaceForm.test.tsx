import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-error";

const refreshTenants = vi.fn().mockResolvedValue(undefined);
const onDone = vi.fn();

const apiMock = vi.hoisted(() => ({ tenants: { update: vi.fn() } }));

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "tenants.name": "Name",
      "tenants.slug": "Identifier",
      "tenants.defaultLocale": "Default language",
      "tenants.answerMode": "Answer mode",
      "tenants.strict": "Strict",
      "tenants.assistive": "Assistive",
      "tenants.status": "Status",
      "tenants.active": "Active",
      "tenants.inactive": "Inactive",
      "tenants.statusHint": "When inactive the chat stops answering.",
      "tenants.saving": "Saving...",
      "common.save": "Save",
      "common.cancel": "Cancel",
      "errors.generic": "Generic error",
      "errors.SLUG_ALREADY_TAKEN": "Slug taken",
    };
    return Object.assign((key: string) => messages[`${namespace}.${key}`] ?? key, {
      has: (key: string) => `${namespace}.${key}` in messages,
    });
  },
}));

vi.mock("@/features/tenants/TenantProvider", () => ({
  useTenant: () => ({ refreshTenants }),
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

import { EditWorkspaceForm } from "@/features/workspaces/EditWorkspaceForm";

const tenant = {
  id: 1,
  name: "Acme",
  slug: "acme",
  default_locale: "it",
  answer_mode: "strict" as const,
  is_active: true,
};

beforeEach(() => {
  refreshTenants.mockClear();
  onDone.mockClear();
  apiMock.tenants.update.mockReset();
  apiMock.tenants.update.mockResolvedValue({ id: 1 });
});

describe("EditWorkspaceForm", () => {
  it("prefills the fields from the workspace", () => {
    render(<EditWorkspaceForm tenant={tenant} onDone={onDone} />);

    expect(screen.getByLabelText("Name")).toHaveValue("Acme");
    expect(screen.getByLabelText("Identifier")).toHaveValue("acme");
    expect(screen.getByLabelText("Default language")).toHaveValue("it");
    expect(screen.getByLabelText("Answer mode")).toHaveValue("strict");
    expect(screen.getByLabelText("Status")).toHaveValue("active");
  });

  it("saves and calls onDone", async () => {
    render(<EditWorkspaceForm tenant={tenant} onDone={onDone} />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "New name" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(apiMock.tenants.update).toHaveBeenCalledWith(1, {
        name: "New name",
        slug: "acme",
        default_locale: "it",
        answer_mode: "strict",
        is_active: true,
      }),
    );
    expect(refreshTenants).toHaveBeenCalled();
    expect(onDone).toHaveBeenCalled();
  });

  it("sends the deactivated status", async () => {
    render(<EditWorkspaceForm tenant={tenant} onDone={onDone} />);

    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "inactive" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(apiMock.tenants.update).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ is_active: false }),
      ),
    );
  });

  it("cancels without saving", () => {
    render(<EditWorkspaceForm tenant={tenant} onDone={onDone} />);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(apiMock.tenants.update).not.toHaveBeenCalled();
    expect(onDone).toHaveBeenCalled();
  });

  it("shows a slug conflict error", async () => {
    apiMock.tenants.update.mockRejectedValue(
      new ApiError(409, { code: "SLUG_ALREADY_TAKEN", message: "taken" }),
    );

    render(<EditWorkspaceForm tenant={tenant} onDone={onDone} />);

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Slug taken"),
    );
    expect(onDone).not.toHaveBeenCalled();
  });
});
