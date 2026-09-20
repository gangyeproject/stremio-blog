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
      candidates.push({ parts: [before, after], distance: Math.abs(count(before) - total / 2) });
    }
    before += token.raw;
  }
  candidates.sort((a, b) => a.distance - b.distance);
  return candidates[0]?.parts || [content];
}
