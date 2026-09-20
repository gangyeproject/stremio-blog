import { marked } from 'marked';

export function splitAddonContent(content = '') {
  const tokens = marked.lexer(content);
  const count = (text) => text.trim().split(/\s+/).filter(Boolean).length;
  const total = count(content);
  if (total < 800) return [content];
  let before = '';
  for (let index = 0; index < tokens.length; index++) {
    const token = tokens[index];
    const after = tokens.slice(index).map(part => part.raw).join('');
    const previous = tokens.slice(0, index).filter(part => part.type !== 'space').at(-1);
    if (token.type === 'heading' && token.depth === 2 && previous?.type === 'paragraph'
      && !/install|download|setup|configur|step|manifest/i.test(token.text)
      && !/https?:|stremio:|\]\(/i.test(previous.raw)
      && count(before) >= Math.max(400, total * 0.5) && count(after) >= 250) {
      return [before, after];
    }
    before += token.raw;
  }
  return [content];
}
