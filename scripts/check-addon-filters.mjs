import assert from 'node:assert/strict';
import { getAddonCategories, getAddonSearchText, getCategoryOptions, matchesAddon, normalizeSearch } from '../src/lib/addon-filters.js';

assert.deepEqual(getAddonCategories({ types: ['movie', 'movies', 'tv shows', 'series'] }), ['movies', 'series']);
assert.deepEqual(getAddonCategories({ types: [' Movie,Series ', 'anime'] }), ['movies', 'series', 'anime']);
assert.deepEqual(getAddonCategories({ types: ['author: someone', null, 123] }), ['other']);
assert.deepEqual(getAddonCategories({}), ['other']);
assert.deepEqual(getAddonCategories({ types: 'movie' }), ['other']);
assert.deepEqual(getCategoryOptions([{ types: ['movie', 'movies'] }, { types: ['movie', 'series'] }, {}]), [
  { id: 'movies', label: 'Movies', count: 2 },
  { id: 'series', label: 'TV Shows', count: 1 },
  { id: 'other', label: 'Other / Uncategorized', count: 1 },
]);
assert.deepEqual(getCategoryOptions([]), []);
const addon = { title: 'Café Stream', sulg: 'cafe-stream', summary: 'French movies', types: ['movie'] };
const text = getAddonSearchText(addon);
assert.ok(matchesAddon(text, ['movies'], '  CAFE   french ', 'movies'));
assert.ok(matchesAddon(text, ['movies'], 'movies', ''));
assert.ok(matchesAddon(text, ['movies'], '', ''));
assert.ok(!matchesAddon(text, ['movies'], 'cafe', 'series'));
assert.ok(!matchesAddon(text, ['movies'], 'not-found', ''));
assert.ok(!matchesAddon(text, ['movies'], '<script>', ''));
assert.equal(normalizeSearch('字幕  插件'), '字幕 插件');
assert.equal(normalizeSearch('ＦＩＬＭ'), 'film');
console.log('Addon search and category checks passed.');
