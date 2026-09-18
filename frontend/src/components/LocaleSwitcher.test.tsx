import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleSwitcher } from "@/components/LocaleSwitcher";

const replace = vi.fn();
let currentLocale = "it";

vi.mock("next-intl", () => ({
  useLocale: () => currentLocale,
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
  it("renders one button per locale with accessible labels", () => {
    render(<LocaleSwitcher />);

    expect(screen.getByRole("button", { name: "Italiano" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "English" })).toBeInTheDocument();
  });

  it("marks the active locale as pressed", () => {
    render(<LocaleSwitcher />);

    expect(screen.getByRole("button", { name: "Italiano" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("navigates to the selected locale", async () => {
    const user = userEvent.setup();
    render(<LocaleSwitcher />);

    await user.click(screen.getByRole("button", { name: "English" }));

    expect(replace).toHaveBeenCalledWith("/login", { locale: "en" });
  });

  it("does not navigate when clicking the active locale", async () => {
    const user = userEvent.setup();
    render(<LocaleSwitcher />);

    await user.click(screen.getByRole("button", { name: "Italiano" }));

    expect(replace).not.toHaveBeenCalled();
  });
});
