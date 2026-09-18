import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Navbar } from "@/components/Navbar";

vi.mock("@/components/LocaleSwitcher", () => ({
  LocaleSwitcher: () => <span data-testid="locale-switcher" />,
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

describe("Navbar", () => {
  it("links the app name to the home page", () => {
    render(<Navbar />);

    expect(screen.getByRole("link", { name: "jac-rag" })).toHaveAttribute("href", "/");
  });

  it("always renders the locale switcher and the provided right slot", () => {
    render(
      <Navbar>
        <button type="button">Options</button>
      </Navbar>,
    );

    expect(screen.getByTestId("locale-switcher")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Options" })).toBeInTheDocument();
  });
});
