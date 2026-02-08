import { marked } from 'marked';

const STRAPI_URL = 'https://admin.stremioaddonmanager.org';
const SITE_DOMAIN = 'stremioaddonmanager.org';

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

export async function getArticles() {
  const res = await fetch(`${STRAPI_URL}/api/articles?populate=cover&sort=createdAt:desc`);
  const data = await res.json();
  return data.data || [];
}

export async function getArticleBySlug(slug) {
  const res = await fetch(`${STRAPI_URL}/api/articles?filters[slug][$eq]=${slug}&populate=cover`);
  const data = await res.json();
  return data.data?.[0] || null;
}

export async function getAllSlugs() {
  const res = await fetch(`${STRAPI_URL}/api/articles?fields[0]=slug`);
  const data = await res.json();
  return data.data?.map(article => article.slug).filter(slug => slug) || [];
}

export function getCoverUrl(article) {
  const cover = article?.cover;
  if (!cover) return null;
  const url = cover.url;
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
