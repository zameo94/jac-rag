import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Breadcrumbs } from "@/components/Breadcrumbs";

const state = vi.hoisted(() => ({ pathname: "/dashboard/documents" }));

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const messages: Record<string, string> = {
      "nav.home": "Home",
      "nav.documents": "Documents",
      "nav.chat": "Chat",
      "nav.conversations": "Conversations",
      "nav.members": "Members",
      "nav.settings": "Settings",
      "nav.workspaces": "Workspaces",
      "workspaces.new": "New workspace",
      "workspaces.editTitle": "Edit workspace",
      "breadcrumbs.label": "Breadcrumb",
    };
    return (key: string) => messages[key] ?? key;
  },
}));

vi.mock("@/i18n/navigation", () => ({
  usePathname: () => state.pathname,
  Link: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

beforeEach(() => {
  state.pathname = "/dashboard/documents";
});

describe("Breadcrumbs", () => {
  it("renders the home crumb linking to the root", () => {
    render(<Breadcrumbs />);

    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
  });

  it("renders nothing for the dashboard root (it is the home page)", () => {
    state.pathname = "/dashboard";

    const { container } = render(<Breadcrumbs />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders the documents section", () => {
    render(<Breadcrumbs />);

    expect(screen.getByText("Documents")).toHaveAttribute("aria-current", "page");
  });

  it("renders the chat section", () => {
    state.pathname = "/dashboard/chat";

    render(<Breadcrumbs />);

    expect(screen.getByText("Chat")).toHaveAttribute("aria-current", "page");
  });

  it("renders the workspaces section", () => {
    state.pathname = "/dashboard/workspaces";

    render(<Breadcrumbs />);

    expect(screen.getByText("Workspaces")).toHaveAttribute("aria-current", "page");
  });

  it("renders the new workspace section", () => {
    state.pathname = "/dashboard/workspaces/new";

    render(<Breadcrumbs />);

    expect(screen.getByText("New workspace")).toHaveAttribute("aria-current", "page");
  });

  it("renders the edit workspace section", () => {
    state.pathname = "/dashboard/workspaces/7/edit";

    render(<Breadcrumbs />);

    expect(screen.getByText("Edit workspace")).toHaveAttribute("aria-current", "page");
  });

  it("renders the members section", () => {
    state.pathname = "/dashboard/members";

    render(<Breadcrumbs />);

    expect(screen.getByText("Members")).toHaveAttribute("aria-current", "page");
  });

  it("renders nothing for routes without a mapping", () => {
    state.pathname = "/login";

    const { container } = render(<Breadcrumbs />);

    expect(container).toBeEmptyDOMElement();
  });
});
