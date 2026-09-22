import { afterEach, describe, expect, it, vi } from "vitest";

import { EMBED_KEY_PLACEHOLDER, widgetSnippet } from "@/lib/widget-embed";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("widgetSnippet", () => {
  it("builds a script tag with the configured urls and the key", () => {
    vi.stubEnv(
      "NEXT_PUBLIC_WIDGET_SCRIPT_URL",
      "https://cdn.example.com/embed-rag-chatbot.js",
    );
    vi.stubEnv("NEXT_PUBLIC_WIDGET_API_URL", "https://api.example.com");

    const snippet = widgetSnippet("jrk_abc");

    expect(snippet).toContain(
      'src="https://cdn.example.com/embed-rag-chatbot.js"',
    );
    expect(snippet).toContain('data-embed-key="jrk_abc"');
    expect(snippet).toContain('data-api-url="https://api.example.com"');
    expect(snippet).toContain("defer");
  });

  it("leaves the urls empty when they are not configured", () => {
    const snippet = widgetSnippet(EMBED_KEY_PLACEHOLDER);

    expect(snippet).toContain('src=""');
    expect(snippet).toContain(`data-embed-key="${EMBED_KEY_PLACEHOLDER}"`);
  });
});
