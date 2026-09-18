import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorMessage } from "@/components/ErrorMessage";
import { ApiError } from "@/lib/api-error";

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const messages: Record<string, string> = {
      generic: "Generic error",
      EMAIL_ALREADY_REGISTERED: "Email already registered",
    };
    const translate = (key: string) => messages[key] ?? key;
    translate.has = (key: string) => key in messages;
    return translate;
  },
}));

describe("ErrorMessage", () => {
  it("renders nothing without error", () => {
    const { container } = render(<ErrorMessage error={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("maps a known api error code to its translation", () => {
    render(<ErrorMessage error={new ApiError(409, { code: "EMAIL_ALREADY_REGISTERED", message: "x" })} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Email already registered");
  });

  it("falls back to generic for unknown codes", () => {
    render(<ErrorMessage error={new ApiError(500, { code: "UNKNOWN_CODE", message: "x" })} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Generic error");
  });

  it("falls back to generic for non-api errors", () => {
    render(<ErrorMessage error={new Error("boom")} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Generic error");
  });
});
