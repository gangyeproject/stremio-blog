import { marked } from 'marked';

export function splitAddonContent(content = '') {
  const tokens = marked.lexer(content);
  const count = (text) => text.trim().split(/\s+/).filter(Boolean).length;
  const total = count(content);
  if (total < 500) return [content];
  const candidates = [];
  let before = '';
  for (let index = 0; index < tokens.length; index++) {
    const token = tokens[index];
    const after = tokens.slice(index).map(part => part.raw).join('');
    const previous = tokens.slice(0, index).filter(part => part.type !== 'space').at(-1);
    if (token.type === 'heading' && token.depth === 2 && ['paragraph', 'list', 'table', 'hr'].includes(previous?.type)
      && !/install|download|setup|configur|step|manifest/i.test(token.text)
      && !(previous.type === 'paragraph' && /https?:|stremio:|\]\(/i.test(previous.raw))
      && count(before) >= 200 && count(after) >= 200) {
      candidates.push({ parts: [before, after], distance: Math.abs(count(before) - total * 0.65) });
    }
    before += token.raw;
  }
  candidates.sort((a, b) => a.distance - b.distance);
  return candidates[0]?.parts || [content];
}

// Keep the opening paragraph intact, and never split a list or tutorial step.
export function getAdContentParts(content = '') {
  const later = splitAddonContent(content);
  const tokens = marked.lexer(later[0]);
  let intro = '';
  for (const token of tokens) {
    intro += token.raw;
    if (token.type === 'paragraph' && !/^\s*!\[/.test(token.raw)) break;
  }
  const rest = later[0].slice(intro.length);
  // Very short content has no useful introduction/body boundary.
  if (!rest.trim()) return [content, ''];
  if (later.length === 2 && rest.trim().split(/\s+/).length >= 150) {
    return [intro, rest, later[1]];
  }
  return [intro, content.slice(intro.length)];
}
