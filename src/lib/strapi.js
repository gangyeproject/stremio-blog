import { marked } from 'marked';

const STRAPI_URL = 'https://admin.stremioaddonmanager.org';
const SITE_DOMAIN = 'stremioaddonmanager.org';
const PAGE_SIZE = 100;

// Configure marked to add nofollow to external links
const renderer = {
  link(token) {
    const href = token.href || '';
    const title = token.title ? ` title="${token.title}"` : '';
    const text = token.text || '';

    if (href && !href.includes(SITE_DOMAIN) && href.startsWith('http')) {
      return `<a href="${href}" rel="nofollow" target="_blank"${title}>${text}</a>`;
    }
    return `<a href="${href}"${title}>${text}</a>`;
  }
};

marked.use({ renderer });

// Articles API
export async function getArticles() {
  const res = await fetch(`${STRAPI_URL}/api/articles?populate=cover&sort=createdAt:desc&pagination[pageSize]=${PAGE_SIZE}`);
  const data = await res.json();
  return data.data || [];
}

export async function getArticleBySlug(slug) {
  const res = await fetch(`${STRAPI_URL}/api/articles?filters[slug][$eq]=${encodeURIComponent(slug)}&populate=cover`);
  const data = await res.json();
  return data.data?.[0] || null;
}

export async function getAllSlugs() {
  const res = await fetch(`${STRAPI_URL}/api/articles?fields[0]=slug&pagination[pageSize]=${PAGE_SIZE}`);
  const data = await res.json();
  return data.data?.map(article => article.slug).filter(slug => slug) || [];
}

// Addons API
export async function getAddons() {
  try {
    const res = await fetch(`${STRAPI_URL}/api/addons?populate=cover&sort=createdAt:desc&pagination[pageSize]=${PAGE_SIZE}`);
    const text = await res.text();
    console.log('[getAddons] status:', res.status, 'body preview:', text.substring(0, 200));
    const data = JSON.parse(text);
    return data.data || [];
  } catch (e) {
    console.error('[getAddons] error:', e);
    return [];
  }
}

export async function getAddonBySlug(sulg) {
  const res = await fetch(`${STRAPI_URL}/api/addons?filters[sulg][$eq]=${encodeURIComponent(sulg)}&populate=cover`);
  const data = await res.json();
  return data.data?.[0] || null;
}

export async function getAllAddonSlugs() {
  const res = await fetch(`${STRAPI_URL}/api/addons?fields[0]=sulg&pagination[pageSize]=${PAGE_SIZE}`);
  const data = await res.json();
  return data.data?.map(addon => addon.sulg).filter(sulg => sulg) || [];
}

// Shared utilities
export function getCoverUrl(item) {
  const cover = item?.cover;
  if (!cover) return null;
  // support both text (string URL) and media object
  if (typeof cover === 'string') {
    return cover.startsWith('http') ? cover : `${STRAPI_URL}${cover}`;
  }
  const url = cover.url;
  if (!url) return null;
  return url.startsWith('http') ? url : `${STRAPI_URL}${url}`;
}

export function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
}

export function renderContent(content) {
  if (!content) return '';
  return marked(content);
}
