import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "workspaces.noneTitle": "You do not belong to any workspace",
      "workspaces.noneHint": "Get invited or create one.",
      "workspaces.noneCta": "Create or join a workspace",
    };
    return (key: string) => messages[`${namespace}.${key}`] ?? key;
  },
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import { NoWorkspaceGate } from "@/features/workspaces/NoWorkspaceGate";

describe("NoWorkspaceGate", () => {
  it("shows the message and a call to action to create a workspace", () => {
    render(<NoWorkspaceGate />);

    expect(
      screen.getByRole("heading", { name: "You do not belong to any workspace" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Get invited or create one.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create or join a workspace" })).toHaveAttribute(
      "href",
      "/dashboard/workspaces/new",
    );
  });
});
