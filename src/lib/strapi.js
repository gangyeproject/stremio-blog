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

  return content.map(block => {
    if (block.type === 'paragraph') {
      const text = block.children.map(child => {
        let t = child.text || '';
        if (child.bold) t = `<strong>${t}</strong>`;
        if (child.italic) t = `<em>${t}</em>`;
        if (child.underline) t = `<u>${t}</u>`;
        if (child.strikethrough) t = `<s>${t}</s>`;
        if (child.code) t = `<code>${t}</code>`;
        if (child.type === 'link') {
          t = `<a href="${child.url}" target="_blank" rel="noopener">${child.children.map(c => c.text).join('')}</a>`;
        }
        return t;
      }).join('');
      return `<p>${text}</p>`;
    }
    if (block.type === 'heading') {
      const level = block.level || 2;
      const text = block.children.map(child => child.text || '').join('');
      return `<h${level}>${text}</h${level}>`;
    }
    if (block.type === 'list') {
      const tag = block.format === 'ordered' ? 'ol' : 'ul';
      const items = block.children.map(item => {
        const text = item.children.map(child => {
          if (child.type === 'text') return child.text || '';
          if (child.children) return child.children.map(c => c.text || '').join('');
          return '';
        }).join('');
        return `<li>${text}</li>`;
      }).join('');
      return `<${tag}>${items}</${tag}>`;
    }
    if (block.type === 'quote') {
      const text = block.children.map(child => child.text || '').join('');
      return `<blockquote>${text}</blockquote>`;
    }
    if (block.type === 'code') {
      const text = block.children.map(child => child.text || '').join('');
      return `<pre><code>${text}</code></pre>`;
    }
    if (block.type === 'image') {
      const url = block.image?.url;
      if (url) {
        const fullUrl = url.startsWith('http') ? url : `${STRAPI_URL}${url}`;
        return `<img src="${fullUrl}" alt="${block.image?.alternativeText || ''}" />`;
      }
    }
    return '';
  }).join('');
}
