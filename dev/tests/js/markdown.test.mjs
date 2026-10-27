import { test } from 'node:test';
import assert from 'node:assert/strict';
import { escapeHTML, renderMarkdownSafe } from '../../../src/frontend/js/markdown.js';

test('escapeHTML escapes all markup chars including quotes', () => {
  assert.equal(escapeHTML(`<a href="x">'&'`),
    '&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;');
  assert.equal(escapeHTML(null), '');
  assert.equal(escapeHTML(''), '');
});

test('image URL cannot break out of src attribute', () => {
  const out = renderMarkdownSafe('![x](https://a"onerror="alert(1))');
  // the quote is escaped to &quot;, so it can't terminate the attribute;
  // a real injected attribute would need whitespace before the name
  assert.ok(!/ onerror=/i.test(out), out);
  assert.ok(out.includes('&quot;'), out);
});

test('link URL cannot break out of href attribute', () => {
  const out = renderMarkdownSafe('[t](https://a"class="x)');
  assert.ok(!/href="[^"]*"class=/i.test(out), out);
});

test('raw HTML in body is escaped, not injected', () => {
  const out = renderMarkdownSafe('hello <img src=x onerror=alert(1)> bye');
  assert.ok(!/<img/.test(out), out);
  assert.ok(out.includes('&lt;img'), out);
});

test('script tags never appear in output', () => {
  const out = renderMarkdownSafe('<script>alert(1)</script>');
  assert.ok(!/<script/i.test(out), out);
});

test('bold, italic, inline code and headings render', () => {
  const out = renderMarkdownSafe('# Title\n\n**bold** and *em* and `code`');
  assert.ok(out.includes('<h1>Title</h1>'), out);
  assert.ok(out.includes('<strong>bold</strong>'), out);
  assert.ok(out.includes('<em>em</em>'), out);
  assert.ok(out.includes('<code>code</code>'), out);
});

test('links are http(s) only and get rel=noopener', () => {
  const out = renderMarkdownSafe('[ok](https://example.com) [no](javascript:alert(1))');
  assert.ok(out.includes('<a href="https://example.com"'), out);
  assert.ok(out.includes('rel="noopener noreferrer"'), out);
  assert.ok(!/href="javascript:/i.test(out), out);
});

test('consecutive list items render as one <ul>', () => {
  const out = renderMarkdownSafe('- one\n- two\n- three');
  assert.equal((out.match(/<ul>/g) || []).length, 1, out);
  assert.equal((out.match(/<li>/g) || []).length, 3, out);
});

test('pipe table renders as <table>', () => {
  const out = renderMarkdownSafe('| a | b |\n|---|---|\n| 1 | 2 |');
  assert.ok(out.includes('<table>'), out);
  assert.ok(out.includes('<th>a</th>'), out);
  assert.ok(out.includes('<td>2</td>'), out);
});

test('text after a list keeps its own paragraph', () => {
  const out = renderMarkdownSafe('- item\n\nOutro text');
  assert.ok(out.includes('<ul>'), out);
  assert.ok(/<p>Outro text<\/p>/.test(out), out);
});

test('code block keeps content escaped', () => {
  const out = renderMarkdownSafe('```\n<div>x</div>\n```');
  assert.ok(out.includes('<pre><code>'), out);
  assert.ok(!/<div>/.test(out), out);
});
