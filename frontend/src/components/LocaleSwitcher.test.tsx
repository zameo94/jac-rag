import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleSwitcher } from "@/components/LocaleSwitcher";

const replace = vi.fn();
let currentLocale = "it";

vi.mock("next-intl", () => ({
  useLocale: () => currentLocale,
  useTranslations: () => (key: string) => (key === "language" ? "Language" : key),
}));

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/login",
}));

beforeEach(() => {
  replace.mockClear();
  currentLocale = "it";
});

describe("LocaleSwitcher", () => {
  it("renders a dropdown trigger with the current locale", () => {
    render(<LocaleSwitcher />);

    const trigger = screen.getByRole("button", { name: "Language" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveTextContent("it");
  });

  it("opens the menu showing all locales", async () => {
    const user = userEvent.setup();
    render(<LocaleSwitcher />);

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Language" }));

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Italiano" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "English" })).toBeInTheDocument();
  });

  it("navigates to the selected locale and closes the menu", async () => {
    const user = userEvent.setup();
    render(<LocaleSwitcher />);

    await user.click(screen.getByRole("button", { name: "Language" }));
    await user.click(screen.getByRole("menuitem", { name: "English" }));

    expect(replace).toHaveBeenCalledWith("/login", { locale: "en" });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("does not navigate when selecting the current locale", async () => {
    const user = userEvent.setup();
    render(<LocaleSwitcher />);

    await user.click(screen.getByRole("button", { name: "Language" }));
    await user.click(screen.getByRole("menuitem", { name: "Italiano" }));

    expect(replace).not.toHaveBeenCalled();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes the menu on Escape", async () => {
    const user = userEvent.setup();
    render(<LocaleSwitcher />);

    await user.click(screen.getByRole("button", { name: "Language" }));
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
