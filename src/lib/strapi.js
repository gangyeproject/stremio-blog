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

async function fetchRecords(collection, query) {
  const response = await fetch(`${STRAPI_URL}/api/${collection}?${query}`);
  if (!response.ok) {
    throw new Error(`Strapi ${collection} request failed: HTTP ${response.status}`);
  }
  const payload = await response.json();
  if (!Array.isArray(payload.data)) {
    throw new Error(`Strapi ${collection} returned an invalid collection`);
  }
  return payload;
}

async function fetchAllRecords(collection, query) {
  const records = [];
  let page = 1;
  let pageCount = 1;
  do {
    const payload = await fetchRecords(collection,
      `${query}&status=published&pagination[pageSize]=${PAGE_SIZE}&pagination[page]=${page}`);
    const pagination = payload.meta?.pagination;
    if (!Number.isInteger(pagination?.pageCount) || pagination.pageCount < 0 ||
        pagination.page !== page || (!payload.data.length && page <= pagination.pageCount)) {
      throw new Error(`Strapi ${collection} returned invalid pagination on page ${page}`);
    }
    records.push(...payload.data);
    pageCount = pagination.pageCount;
    page += 1;
  } while (page <= pageCount);
  return records;
}

// Articles API
export async function getArticles() {
  return fetchAllRecords('articles', 'populate=cover&sort[0]=createdAt:desc&sort[1]=id:desc');
}

export async function getArticleBySlug(slug) {
  const data = await fetchRecords('articles', `filters[slug][$eq]=${encodeURIComponent(slug)}&populate=cover&status=published`);
  return data.data?.[0] || null;
}

export async function getAllSlugs() {
  const records = await fetchAllRecords('articles', 'fields[0]=slug&sort=id:asc');
  return [...new Set(records.map(article => article.slug).filter(Boolean))];
}

// Addons API
export async function getAddons() {
  return fetchAllRecords('addons', 'populate=cover&sort[0]=createdAt:desc&sort[1]=id:desc');
}

export async function getAddonBySlug(sulg) {
  const data = await fetchRecords('addons', `filters[sulg][$eq]=${encodeURIComponent(sulg)}&populate=cover&status=published`);
  return data.data?.[0] || null;
}

export async function getAllAddonSlugs() {
  const records = await fetchAllRecords('addons', 'fields[0]=sulg&sort=id:asc');
  return [...new Set(records.map(addon => addon.sulg).filter(Boolean))];
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
