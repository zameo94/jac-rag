export const EMBED_KEY_PLACEHOLDER = "YOUR_EMBED_KEY";

export function widgetSnippet(embedKey: string): string {
  const scriptUrl = process.env.NEXT_PUBLIC_WIDGET_SCRIPT_URL ?? "";
  const apiUrl = process.env.NEXT_PUBLIC_WIDGET_API_URL ?? "";
  return [
    "<script",
    `  src="${scriptUrl}"`,
    `  data-embed-key="${embedKey}"`,
    `  data-api-url="${apiUrl}"`,
    "  defer",
    "></script>",
  ].join("\n");
}
