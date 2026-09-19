import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Breadcrumbs } from "@/components/Breadcrumbs";

const state = vi.hoisted(() => ({ pathname: "/dashboard" }));

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const messages: Record<string, string> = {
      "nav.home": "Home",
      "nav.documents": "Documents",
      "nav.members": "Members",
      "nav.settings": "Settings",
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
  state.pathname = "/dashboard";
});

describe("Breadcrumbs", () => {
  it("renders the home crumb linking to the root", () => {
    render(<Breadcrumbs />);

    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
  });

  it("renders the current section for the dashboard root", () => {
    render(<Breadcrumbs />);

    const current = screen.getByText("Documents");
    expect(current).toHaveAttribute("aria-current", "page");
  });

  it("renders the members section", () => {
    state.pathname = "/dashboard/members";

    render(<Breadcrumbs />);

    expect(screen.getByText("Members")).toHaveAttribute("aria-current", "page");
  });

  it("renders the settings section", () => {
    state.pathname = "/dashboard/settings";

    render(<Breadcrumbs />);

    expect(screen.getByText("Settings")).toHaveAttribute("aria-current", "page");
  });

  it("renders nothing for routes without a mapping", () => {
    state.pathname = "/login";

    const { container } = render(<Breadcrumbs />);

    expect(container).toBeEmptyDOMElement();
  });
});
