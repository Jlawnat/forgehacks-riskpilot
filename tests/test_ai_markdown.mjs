import assert from "node:assert/strict";
import test from "node:test";
import { parseInline, parseMarkdownBlocks } from "../web/src/aiMarkdown.js";

test("renders strong emphasis and negative money figures without changing data", () => {
  const tokens = parseInline("**Minimum reserve headroom:** **-$10,685,000**");
  assert.deepEqual(tokens, [
    { type: "strong", text: "Minimum reserve headroom:" },
    { type: "text", text: " " },
    { type: "strong", text: "-$10,685,000" },
  ]);
});

test("recognizes real AI response bullets and paragraphs", () => {
  const text = "Your current position is **high risk**:\n\n- **Current cash:** $26,749,000\n- **Management reserve:** $20,000,000\n\nThe position recovers later.";
  const blocks = parseMarkdownBlocks(text);
  assert.equal(blocks.length, 3);
  assert.equal(blocks[0].type, "paragraph");
  assert.equal(blocks[1].type, "unordered");
  assert.equal(blocks[1].items.length, 2);
  assert.equal(blocks[2].type, "paragraph");
});

test("supports headings, code fences and quotes", () => {
  const blocks = parseMarkdownBlocks("### Findings\n\n```json\n{\"verified\": true}\n```\n\n> Source evidence only");
  assert.deepEqual(blocks.map(x => x.type), ["heading", "codeblock", "blockquote"]);
  assert.equal(blocks[1].text, '{"verified": true}');
});

test("does not convert untrusted HTML or javascript URLs into DOM structures", () => {
  const tokens = parseInline("<img src=x onerror=alert(1)> [click](javascript:alert(1))");
  assert(tokens.every(x => x.type === "text"));
});

test("supports GFM-style ordered lists and ordinary safe links", () => {
  const blocks = parseMarkdownBlocks("1. First check\n2. Second check");
  assert.equal(blocks[0].type, "ordered");
  const tokens = parseInline("Read [official evidence](https://example.com/data).");
  assert.equal(tokens[1].type, "link");
  assert.equal(tokens[1].url, "https://example.com/data");
});
