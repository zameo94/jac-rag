import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HomeContent } from "@/features/home/HomeContent";

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "home.title": "Your documents",
      "home.subtitle": "Upload your files",
      "home.cta": "Go to documents",
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

describe("HomeContent", () => {
  it("renders the hero copy", () => {
    render(<HomeContent />);

    expect(screen.getByRole("heading", { name: "Your documents" })).toBeInTheDocument();
    expect(screen.getByText("Upload your files")).toBeInTheDocument();
  });

  it("renders a call to action pointing to documents", () => {
    render(<HomeContent />);

    expect(screen.getByRole("link", { name: "Go to documents" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });
});
