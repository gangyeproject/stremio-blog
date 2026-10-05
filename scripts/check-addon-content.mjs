import assert from 'node:assert/strict';
import { getAddonIcon, getAddonInitials, isManifestUrl, prepareAddonContent, renderAddonContent } from '../src/lib/addon-content.js';

const image = 'https://cdn.example.com/addon.png';
const content = `Short introduction.\n\n## Features\n\n- **Schedules:** Retro television.\n- **Lists:** Daily picks.\n\n![Addon logo](${image})\n\n[Source listing](https://source.example.com/addon)`;
const addon = { sulg: 'now-showing', content, cover: null };
assert.equal(getAddonIcon(addon), image);
assert.equal(getAddonIcon({ ...addon, cover: { url: '/cover.png' } }), 'https://admin.stremioaddonmanager.org/cover.png');
assert.equal(getAddonIcon({ content: 'No image.' }), null);
assert.equal(getAddonIcon({ content: '![Bad logo](javascript:alert)' }), null);
assert.equal(getAddonInitials(addon), 'NS');
const prepared = prepareAddonContent(content, image);
assert.doesNotMatch(prepared, /Source listing|addon\.png/);
assert.match(prepared, /## Features/);
const rendered = renderAddonContent(prepared);
assert.match(rendered, /<h2>Features<\/h2>/);
assert.match(rendered, /<ul>/);
assert.match(rendered, /<strong>Schedules:<\/strong>/);
assert.match(rendered, /<p>Short introduction\.<\/p>/);
assert.equal((rendered.match(/<li>/g) || []).length, 2);

for (const url of ['https://addon.example.com/manifest.json', 'https://addon.example.com/key/manifest.json?lang=en', 'stremio://addon.example.com/manifest.json']) {
  assert.equal(isManifestUrl(url), true);
  assert.match(renderAddonContent(`[Manifest](${url})`), /<a href=/);
}
for (const url of ['https://source.example.com', 'https://source.example.com/manifest.json/not-manifest', 'https://source.example.com/?next=manifest.json', 'javascript:alert(1)', '/manifest.json']) {
  assert.equal(isManifestUrl(url), false);
  assert.doesNotMatch(renderAddonContent(`[Details](${url})`), /<a\s/);
}
const mixed = renderAddonContent('[Source listing](https://source.example.com)\n\nhttps://source.example.com\n\n[Provider](https://provider.example.com) offers catalogues.\n\n<a href="https://source.example.com">Source listing</a>\n\n<a href="https://addon.example.com/manifest.json">Manifest</a>\n\n<script>alert(1)</script>');
assert.doesNotMatch(mixed, /source\.example|Source listing|provider\.example|script|alert/);
assert.match(mixed, /Provider/);
assert.equal((mixed.match(/<a href=/g) || []).length, 1);
assert.match(renderAddonContent(`![Logo](${image})`), /<img[^>]+src=/);
assert.doesNotMatch(renderAddonContent('# Repeated title'), /<h1>/);
console.log('Addon content checks passed: icons, source removal, manifest-only links, safe HTML, and Markdown structure.');
