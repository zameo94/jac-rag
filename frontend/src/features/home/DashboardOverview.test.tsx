import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "overview.title": "Overview",
      "overview.subtitle": "Everything in your workspace",
      "overview.documents": "Documents",
      "overview.documentsHint": "Files",
      "overview.chat": "Chat",
      "overview.chatHint": "Ask",
      "overview.conversations": "Conversations",
      "overview.conversationsHint": "History",
      "overview.members": "Members",
      "overview.membersHint": "People",
      "overview.settings": "Settings",
      "overview.settingsHint": "Config",
      "overview.workspaces": "Workspaces",
      "overview.workspacesHint": "Spaces",
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

import { DashboardOverview } from "@/features/home/DashboardOverview";

describe("DashboardOverview", () => {
  it("renders the title", () => {
    render(<DashboardOverview />);

    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
  });

  it("renders a card per section with the right link", () => {
    render(<DashboardOverview />);

    const expected: [RegExp, string][] = [
      [/Documents/, "/dashboard/documents"],
      [/Chat/, "/dashboard/chat"],
      [/Conversations/, "/dashboard/conversations"],
      [/Members/, "/dashboard/members"],
      [/Settings/, "/dashboard/settings"],
      [/Workspaces/, "/dashboard/workspaces"],
    ];

    for (const [name, href] of expected) {
      const link = screen.getByRole("link", { name });
      expect(link).toHaveAttribute("href", href);
      expect(link.querySelector("svg")).not.toBeNull();
    }
  });
});
