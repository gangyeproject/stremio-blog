import assert from 'node:assert/strict';
import { getAddons, getArticles, renderContent } from '../src/lib/strapi.js';
import { splitAddonContent } from '../src/lib/addon-ad.js';

for (const [category, items] of [['addons', await getAddons()], ['articles', await getArticles()]]) {
  const double = [];
  for (const item of items) {
    const content = item.content || '';
    const parts = splitAddonContent(content);
    assert.equal(parts.join(''), content);
    assert.equal(parts.map(renderContent).join('').replace(/\s+/g, ' '), renderContent(content).replace(/\s+/g, ' '), item.sulg || item.slug);
    if (parts.length === 2) double.push(item.sulg || item.slug);
  }
  console.log(JSON.stringify({ category, total: items.length, twoAds: double }));
}
