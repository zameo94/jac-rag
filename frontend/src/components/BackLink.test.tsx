import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import { BackButton, BackLink } from "@/components/BackLink";

describe("BackLink", () => {
  it("renders a link to the given href", () => {
    render(<BackLink href="/dashboard/workspaces" />);

    expect(screen.getByRole("link", { name: "back" })).toHaveAttribute(
      "href",
      "/dashboard/workspaces",
    );
  });
});

describe("BackButton", () => {
  it("calls onClick", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(<BackButton onClick={onClick} />);

    await user.click(screen.getByRole("button", { name: "back" }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
