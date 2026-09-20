import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import assert from 'node:assert/strict';

const expected = {
  '9291007289': ['auto', null],
  '7278792318': ['fluid', null],
  '5087719225': ['fluid', 'in-article'],
  '3066421469': ['autorelaxed', null],
};
const counts = {};
function walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) { walk(path); continue; }
    if (!path.endsWith('.html')) continue;
    const html = readFileSync(path, 'utf8');
    const name = relative('dist', path).replaceAll('\\', '/');
    const tags = [...html.matchAll(/<ins\b[^>]*>/g)].map(m => m[0]);
    assert.equal((html.match(/pagead\/js\/adsbygoogle\.js/g) || []).length, 1, name);
    for (const tag of tags) {
      const attrs = Object.fromEntries([...tag.matchAll(/([\w-]+)="([^"]*)"/g)].map(m => [m[1], m[2]]));
      const specification = expected[attrs['data-ad-slot']];
      assert.ok(specification, name + ': unexpected slot');
      assert.equal(attrs['data-ad-client'], 'ca-pub-3421131375387199');
      assert.equal(attrs['data-ad-format'], specification[0]);
      assert.equal(attrs['data-ad-layout'] || null, specification[1]);
      if (attrs['data-ad-slot'] === '7278792318') assert.equal(attrs['data-ad-layout-key'], '-fb+5w+4e-db+86');
      if (attrs['data-ad-slot'] === '9291007289') assert.equal(attrs['data-full-width-responsive'], 'true');
    }
    const category = name === 'addons/index.html' ? 'Addon list' : name.startsWith('addons/') ? 'Addon detail' : name === 'index.html' || name.startsWith('page/') ? 'Blog list' : 'Blog article';
    if (category.endsWith('list') && tags.length) {
      const beforeAd = html.slice(0, html.indexOf('<ins'));
      assert.equal((beforeAd.match(/class="(?:blog|addon)-card"/g) || []).length, 3, name + ': feed must follow third card');
    }
    if (category === 'Addon detail' || category === 'Blog article') {
      const start = html.search(/class="(?:addon-article__content|article__content)"/);
      const beforeAd = html.slice(start, html.indexOf('<ins', start));
      const introductoryText = beforeAd.replace(/<(blockquote|ul|ol|table)\b[^>]*>[\s\S]*?<\/\1>/g, '');
      const textParagraphs = [...introductoryText.matchAll(/<p\b[^>]*>([\s\S]*?)<\/p>/g)]
        .filter(match => !/^\s*<img\b/.test(match[1]) && match[1].replace(/<[^>]*>/g, '').trim());
      assert.ok(textParagraphs.length <= 1, name + ': first ad must follow introduction');
    }
    assert.ok(tags.length <= (category === 'Blog list' ? 1 : 2), name + ': too many ads');
    if (category.endsWith('detail') || category === 'Blog article') assert.ok(tags.length >= 1, name + ': missing ad');
    const key = `${category}: ${tags.length} ads`;
    counts[key] = (counts[key] || 0) + 1;
  }
}
walk('dist');
console.log(counts);
