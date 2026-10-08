// Minimal, dependency-free parser for AI responses.
// This module returns inert data, never executable HTML.
const INLINE = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*(.+?)\*\*|__(.+?)__|`([^`]+)`|~~(.+?)~~|\*([^*\n]+)\*|_([^_\n]+)_/g;

export function parseInline(value) {
  const input = String(value ?? "");
  const tokens = [];
  const matcher = new RegExp(INLINE.source, "g");
  let cursor = 0;
  let match;
  while ((match = matcher.exec(input)) !== null) {
    if (match.index > cursor) {
      tokens.push({ type: "text", text: input.slice(cursor, match.index) });
    }
    if (match[1] && match[2]) {
      tokens.push({ type: "link", text: match[1], url: match[2] });
    } else if (match[3] || match[4]) {
      tokens.push({ type: "strong", text: match[3] ?? match[4] });
    } else if (match[5]) {
      tokens.push({ type: "code", text: match[5] });
    } else if (match[6]) {
      tokens.push({ type: "strike", text: match[6] });
    } else {
      tokens.push({ type: "em", text: match[7] ?? match[8] });
    }
    cursor = matcher.lastIndex;
  }
  if (cursor < input.length) {
    tokens.push({ type: "text", text: input.slice(cursor) });
  }
  return tokens;
}

export function parseMarkdownBlocks(source) {
  const lines = String(source ?? "").replace(/\r\n?/g, "\n").split("\n");
  const result = [];
  let paragraph = [];
  const flushParagraph = () => {
    if (paragraph.length) {
      result.push({ type: "paragraph", lines: paragraph });
      paragraph = [];
    }
  };

  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    const trimmed = line.trim();
    if (!trimmed) { flushParagraph(); i++; continue; }

    const fence = /^\s*(```+|~~~+)(.*)$/.exec(line);
    if (fence) {
      flushParagraph();
      const body = [];
      i++;
      const end = new RegExp(`^\\s*${fence[1][0]}{${fence[1].length},}\\s*$`);
      while (i < lines.length && !end.test(lines[i])) body.push(lines[i++]);
      if (i < lines.length) i++;
      result.push({ type: "codeblock", language: fence[2].trim(), text: body.join("\n") });
      continue;
    }

    const heading = /^\s*(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      result.push({ type: "heading", level: heading[1].length, text: heading[2] });
      i++; continue;
    }

    const bullet = /^\s*([-*+])\s+(.+)$/.exec(line);
    const numbered = /^\s*(\d+)[.)]\s+(.+)$/.exec(line);
    if (bullet || numbered) {
      flushParagraph();
      const type = bullet ? "unordered" : "ordered";
      const items = [];
      const start = numbered ? Number(numbered[1]) : undefined;
      while (i < lines.length) {
        const candidate = lines[i];
        const matched = type === "unordered"
          ? /^\s*[-*+]\s+(.+)$/.exec(candidate)
          : /^\s*\d+[.)]\s+(.+)$/.exec(candidate);
        if (!matched) break;
        items.push(matched[1]);
        i++;
      }
      result.push({ type, items, start });
      continue;
    }

    const quote = /^\s*>\s?(.*)$/.exec(line);
    if (quote) {
      flushParagraph();
      const parts = [];
      while (i < lines.length) {
        const match = /^\s*>\s?(.*)$/.exec(lines[i]);
        if (!match) break;
        parts.push(match[1]);
        i++;
      }
      result.push({ type: "blockquote", lines: parts });
      continue;
    }

    paragraph.push(line.trim());
    i++;
  }
  flushParagraph();
  return result;
}
