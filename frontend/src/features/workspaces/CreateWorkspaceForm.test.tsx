import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const refreshWorkspaces = vi.fn().mockResolvedValue(undefined);
const selectWorkspace = vi.fn();

const apiMock = vi.hoisted(() => ({ workspaces: { create: vi.fn() } }));

vi.mock("next-intl", () => ({
  useLocale: () => "it",
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "workspaces.name": "Name",
      "workspaces.slug": "Identifier",
      "workspaces.slugPlaceholder": "If empty, generated from the name",
      "workspaces.defaultLocale": "Default language",
      "workspaces.answerMode": "Answer mode",
      "workspaces.strict": "Strict",
      "workspaces.assistive": "Assistive",
      "workspaces.createCta": "Create workspace",
    };
    return (key: string) => messages[`${namespace}.${key}`] ?? key;
  },
}));

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/features/workspaces/WorkspaceProvider", () => ({
  useWorkspace: () => ({ refreshWorkspaces, selectWorkspace }),
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

import { CreateWorkspaceForm } from "@/features/workspaces/CreateWorkspaceForm";

beforeEach(() => {
  push.mockClear();
  refreshWorkspaces.mockClear();
  selectWorkspace.mockClear();
  apiMock.workspaces.create.mockReset();
  apiMock.workspaces.create.mockResolvedValue({ id: 5, name: "Acme", slug: "acme" });
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
      expect(apiMock.workspaces.create).toHaveBeenCalledWith("Acme", "", "it", "strict"),
    );
    await waitFor(() => expect(refreshWorkspaces).toHaveBeenCalled());
    expect(selectWorkspace).toHaveBeenCalledWith(5);
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
      expect(apiMock.workspaces.create).toHaveBeenCalledWith(
        "Acme",
        "",
        "it",
        "assistive",
      ),
    );
  });
});
