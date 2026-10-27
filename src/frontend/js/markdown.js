// markdown.js - shared, escaped Markdown rendering and HTML escaping.
// Single source of truth: used by post.html (posts+replies), create.html and ai.js.

// Quotes must be escaped too: image/link URLs and alt text end up inside
// double-quoted attributes, and an unescaped " lets a post inject event handlers.
export function escapeHTML(s){
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// Safe markdown rendering: escape HTML first, then apply basic Markdown.
export function renderMarkdownSafe(src){
  let m = escapeHTML(src||'');
  // headings (support #, ##, ### at line start)
  m = m.replace(/^###\s+(.+)$/gm, '<h3>$1<\/h3>');
  m = m.replace(/^##\s+(.+)$/gm, '<h2>$1<\/h2>');
  m = m.replace(/^#\s+(.+)$/gm, '<h1>$1<\/h1>');
  // code blocks ```...
  m = m.replace(/```([\s\S]*?)```/g, (match, p1) => `<pre><code>${p1.replace(/\n/g,'<br>')}<\/code><\/pre>`);
  // inline code `code`
  m = m.replace(/`([^`]+)`/g, '<code>$1<\/code>');
  // bold and italic
  m = m.replace(/\*\*([^*]+)\*\*/g, '<strong>$1<\/strong>');
  m = m.replace(/\*([^*]+)\*/g, '<em>$1<\/em>');
  // images ![alt](url) – allow only http(s) or /uploads paths
  m = m.replace(/!\[([^\]]*)\]\((https?:[^)\s]+|\/uploads\/[^^)\s]+)\)/g, '<img src="$2" alt="$1" loading="lazy">');
  // links [text](url)
  m = m.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1<\/a>');
  // tables (GFM pipe tables: header row, --- separator row, body rows)
  m = m.replace(/^\|.*\|[ \t]*\n\|(?:[ \t]*:?-{3,}:?[ \t]*\|)+[ \t]*(?:\n\|.*\|[ \t]*)*/gm, (block) => {
    const rows = block.trim().split('\n').map(r => r.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim()));
    const [head, , ...bodyRows] = rows;
    const th = head.map(c => `<th>${c}<\/th>`).join('');
    const tb = bodyRows.map(r => `<tr>${r.map(c => `<td>${c}<\/td>`).join('')}<\/tr>`).join('');
    return `<div class="table-wrap"><table><thead><tr>${th}<\/tr><\/thead><tbody>${tb}<\/tbody><\/table><\/div>\n\n`;
  });
  // unordered lists
  // (one <ul> per run of "- " lines; the trailing blank line keeps the next
  // paragraph separate)
  m = m.replace(/^(?:-[ \t]+.+(?:\n|$))+/gm, (block) => {
    const items = block.trim().split(/\n/).map(l => l.replace(/^-[ \t]+/, '')).map(t => `<li>${t}<\/li>`).join('');
    return `<ul>${items}<\/ul>\n\n`;
  });
  // paragraphs: wrap lines separated by blank lines
  m = m.replace(/(^|\n)\n+/g, '\n\n');
  m = m.split(/\n\n+/).filter(p => p.trim()).map(p => p.match(/^<h[1-3]>|^<ul>|^<pre>|^<div class="table-wrap">/) ? p : `<p>${p.replace(/\n/g,'<br>')}<\/p>`).join('');
  return m;
}
