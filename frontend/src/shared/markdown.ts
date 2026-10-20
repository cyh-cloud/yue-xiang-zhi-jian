export interface MarkdownBlock {
  type: "heading" | "list" | "paragraph";
  text: string;
}

export function toMarkdownBlocks(text: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const plain = line.replace(/\*\*(.+?)\*\*/g, "$1");
    if (/^#{1,3}\s+/.test(plain)) {
      blocks.push({
        type: "heading",
        text: plain.replace(/^#{1,3}\s+/, ""),
      });
    } else if (/^[-*]\s+/.test(plain)) {
      blocks.push({
        type: "list",
        text: plain.replace(/^[-*]\s+/, ""),
      });
    } else {
      blocks.push({ type: "paragraph", text: plain });
    }
  }
  return blocks;
}
