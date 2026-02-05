import { marked } from 'marked';

const STRAPI_URL = 'https://admin.stremioaddonmanager.org';

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
  return data.data?.map(article => article.slug) || [];
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
