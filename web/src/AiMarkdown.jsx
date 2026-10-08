import React from "react";
import { parseInline, parseMarkdownBlocks } from "./aiMarkdown.js";

function Inline({ text }) {
  return parseInline(text).map((token, index) => {
    const key = index;
    switch (token.type) {
      case "strong": return <strong key={key}>{token.text}</strong>;
      case "em": return <em key={key}>{token.text}</em>;
      case "code": return <code key={key}>{token.text}</code>;
      case "strike": return <del key={key}>{token.text}</del>;
      case "link": return (
        <a key={key} href={token.url} target="_blank" rel="noopener noreferrer">
          {token.text}
        </a>
      );
      default: return <React.Fragment key={key}>{token.text}</React.Fragment>;
    }
  });
}

export default function AiMarkdown({ text }) {
  const blocks = parseMarkdownBlocks(text);
  return (
    <div className="ai-markdown">
      {blocks.map((block, index) => {
        const key = index;
        if (block.type === "heading") {
          const Tag = `h${Math.min(block.level + 2, 6)}`;
          return <Tag key={key}><Inline text={block.text} /></Tag>;
        }
        if (block.type === "paragraph") {
          return <p key={key}>
            {block.lines.map((line, lineIndex) => (
              <React.Fragment key={lineIndex}>
                {lineIndex > 0 && <br />}
                <Inline text={line} />
              </React.Fragment>
            ))}
          </p>;
        }
        if (block.type === "unordered" || block.type === "ordered") {
          const Tag = block.type === "ordered" ? "ol" : "ul";
          return <Tag key={key} start={block.start}>
            {block.items.map((item, itemIndex) => (
              <li key={itemIndex}><Inline text={item} /></li>
            ))}
          </Tag>;
        }
        if (block.type === "blockquote") {
          return <blockquote key={key}>
            {block.lines.map((line, lineIndex) => (
              <p key={lineIndex}><Inline text={line} /></p>
            ))}
          </blockquote>;
        }
        if (block.type === "codeblock") {
          return <pre key={key}><code>{block.text}</code></pre>;
        }
        return null;
      })}
    </div>
  );
}
