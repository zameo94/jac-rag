import { afterEach, describe, expect, it, vi } from "vitest";

import { EMBED_KEY_PLACEHOLDER, widgetScriptUrl, widgetSnippet } from "@/lib/widget-embed";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("widgetScriptUrl", () => {
  it("returns the configured url, trimmed", () => {
    vi.stubEnv(
      "NEXT_PUBLIC_WIDGET_SCRIPT_URL",
      "  https://widget.example.com/embed-rag-chatbot.js  ",
    );

    expect(widgetScriptUrl()).toBe(
      "https://widget.example.com/embed-rag-chatbot.js",
    );
  });

  it("returns null when it is missing or blank", () => {
    expect(widgetScriptUrl()).toBeNull();

    vi.stubEnv("NEXT_PUBLIC_WIDGET_SCRIPT_URL", "   ");
    expect(widgetScriptUrl()).toBeNull();
  });
});

describe("widgetSnippet", () => {
  it("builds a script tag with the url and the key", () => {
    const snippet = widgetSnippet(
      EMBED_KEY_PLACEHOLDER,
      "https://widget.example.com/embed-rag-chatbot.js",
    );

    expect(snippet).toContain(
      'src="https://widget.example.com/embed-rag-chatbot.js"',
    );
    expect(snippet).toContain(`data-embed-key="${EMBED_KEY_PLACEHOLDER}"`);
    expect(snippet).toContain("defer");
    expect(snippet).not.toContain("data-api-url");
  });
});
