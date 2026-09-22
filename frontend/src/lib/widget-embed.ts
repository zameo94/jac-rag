export const EMBED_KEY_PLACEHOLDER = "YOUR_EMBED_KEY";

export function widgetScriptUrl(): string | null {
  const url = process.env.NEXT_PUBLIC_WIDGET_SCRIPT_URL?.trim();
  return url ? url : null;
}

export function widgetSnippet(embedKey: string, scriptUrl: string): string {
  return [
    "<script",
    `  src="${scriptUrl}"`,
    `  data-embed-key="${embedKey}"`,
    "  defer",
    "></script>",
  ].join("\n");
}
