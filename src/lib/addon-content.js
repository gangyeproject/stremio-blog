import { Marked } from 'marked';
import sanitizeHtml from 'sanitize-html';
import { getCoverUrl } from './strapi.js';

const markdown = new Marked();
const sourceLabel = /^(?:source(?: listing| list| link| code)?|original source|来源(?:链接)?)\s*:?$/i;

export function isManifestUrl(value = '') {
  try {
    const url = new URL(value);
    return ['https:', 'http:', 'stremio:'].includes(url.protocol) &&
      /\/manifest\.json$/i.test(url.pathname);
  } catch {
    return false;
  }
}

function imageUrl(value = '') {
  if (value.startsWith('/') && !value.startsWith('//')) return value;
  try {
    return ['https:', 'http:'].includes(new URL(value).protocol) ? value : null;
  } catch {
    return null;
  }
}

export function getAddonIcon(addon) {
  const cover = getCoverUrl(addon);
  if (cover && imageUrl(cover)) return cover;
  let logo = null;
  let firstImage = null;
  markdown.walkTokens(markdown.lexer(addon?.content || ''), token => {
    if (token.type !== 'image' || !imageUrl(token.href)) return;
    firstImage ||= token.href;
    if (/logo|icon/i.test(token.text)) logo ||= token.href;
  });
  return logo || firstImage;
}

export function getAddonInitials(addon) {
  return (addon.sulg || addon.title || 'Addon').split(/[\s-]+/)
    .filter(Boolean).slice(0, 2).map(word => Array.from(word)[0]).join('').toUpperCase();
}

export function prepareAddonContent(content = '', iconUrl = null) {
  const tokens = markdown.lexer(content.replace(/\r\n?/g, '\n'));
  let output = content.replace(/\r\n?/g, '\n');
  markdown.walkTokens(tokens, token => {
    if (token.type === 'image' && token.href === iconUrl) output = output.replace(token.raw, '');
  });
  return output.replace(/^\s*\[(?:Source listing|Source list|Source link|Original source)\]\([^\n]+\)\s*$/gim, '')
    .replace(/\n{3,}/g, '\n\n').trim();
}

export function renderAddonContent(content = '') {
  const rendered = markdown.parse(content);
  return sanitizeHtml(rendered, {
    allowedTags: [...sanitizeHtml.defaults.allowedTags, 'img'],
    allowedAttributes: {
      a: ['href', 'rel'],
      img: ['src', 'alt', 'title', 'loading', 'decoding'],
      th: ['colspan', 'rowspan'],
      td: ['colspan', 'rowspan'],
    },
    allowedSchemes: ['http', 'https', 'stremio'],
    allowProtocolRelative: false,
    transformTags: {
      a(tagName, attributes) {
        return isManifestUrl(attributes.href)
          ? { tagName, attribs: { href: attributes.href, rel: 'nofollow noopener noreferrer' } }
          : { tagName: 'span', attribs: {} };
      },
      img(tagName, attributes) {
        return { tagName, attribs: { ...attributes, loading: 'lazy', decoding: 'async' } };
      },
      h1: 'h2',
    },
    exclusiveFilter(frame) {
      if (['a', 'span'].includes(frame.tag) && !isManifestUrl(frame.attribs.href) &&
          (sourceLabel.test(frame.text.trim()) || /^(?:https?:\/\/|www\.)\S+$/i.test(frame.text.trim()))) return true;
      return frame.tag === 'p' && !frame.text.trim() && !frame.mediaChildren.length;
    },
  });
}
