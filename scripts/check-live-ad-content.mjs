import assert from 'node:assert/strict';
import { getAddons, getArticles, renderContent } from '../src/lib/strapi.js';
import { getAdContentParts } from '../src/lib/addon-ad.js';

for (const [category, items] of [['addons', await getAddons()], ['articles', await getArticles()]]) {
  const double = [];
  for (const item of items) {
    const content = item.content || '';
    const parts = getAdContentParts(content);
    assert.equal(parts.join(''), content);
    assert.equal(parts.map(renderContent).join('').replace(/\s+/g, ' '), renderContent(content).replace(/\s+/g, ' '), item.sulg || item.slug);
    if (parts.length === 3) double.push(item.sulg || item.slug);
  }
  console.log(JSON.stringify({ category, total: items.length, twoAds: double }));
}
