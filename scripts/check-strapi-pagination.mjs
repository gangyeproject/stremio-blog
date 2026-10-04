import assert from 'node:assert/strict';
import { getAddons, getAllAddonSlugs, getArticles, getAllSlugs, getAddonBySlug } from '../src/lib/strapi.js';

const originalFetch = globalThis.fetch;
const addonRecords = Array.from({ length: 103 }, (_, index) => ({
  id: index + 1,
  sulg: index >= 100 ? ['popcorn-subs', 'pictorium', 'wlatino'][index - 100] : `addon-${index + 1}`,
}));
const articleRecords = Array.from({ length: 205 }, (_, index) => ({ id: index + 1, slug: `article-${index + 1}` }));
const requests = [];

try {
  globalThis.fetch = async input => {
    const url = new URL(input);
    requests.push(url);
    const records = url.pathname.endsWith('/addons') ? addonRecords : articleRecords;
    const page = Number(url.searchParams.get('pagination[page]'));
    const pageSize = Number(url.searchParams.get('pagination[pageSize]'));
    assert.equal(url.searchParams.get('status'), 'published');
    return Response.json({
      data: records.slice((page - 1) * pageSize, page * pageSize),
      meta: { pagination: { page, pageSize, pageCount: Math.ceil(records.length / pageSize), total: records.length } },
    });
  };
  assert.deepEqual(await getAllAddonSlugs(), addonRecords.map(addon => addon.sulg));
  assert.equal((await getAddons()).length, 103);
  assert.deepEqual(await getAllSlugs(), articleRecords.map(article => article.slug));
  assert.equal((await getArticles()).length, 205);
  assert.equal(requests.length, 10);

  globalThis.fetch = async () => Response.json({ data: [], meta: { pagination: { page: 1, pageCount: 0 } } });
  assert.deepEqual(await getAddons(), []);
  globalThis.fetch = async () => new Response('Unavailable', { status: 503 });
  await assert.rejects(getAddons, /HTTP 503/);
  await assert.rejects(() => getAddonBySlug('pictorium'), /HTTP 503/);
  globalThis.fetch = async () => Response.json({ error: 'Bad response' });
  await assert.rejects(getAllAddonSlugs, /invalid collection/);
  globalThis.fetch = async () => Response.json({ data: addonRecords.slice(0, 100) });
  await assert.rejects(getAllAddonSlugs, /invalid pagination/);
  globalThis.fetch = async input => {
    const page = Number(new URL(input).searchParams.get('pagination[page]'));
    if (page === 2) return new Response('Unavailable', { status: 503 });
    return Response.json({ data: addonRecords.slice(0, 100), meta: { pagination: { page: 1, pageCount: 2 } } });
  };
  await assert.rejects(getAllAddonSlugs, /HTTP 503/);
  console.log('Strapi checks passed: 103 addons, 205 articles, empty collections, malformed data, and failed later pages.');
} finally {
  globalThis.fetch = originalFetch;
}
