const assert = require('node:assert/strict');
const hooks = require('./strapi-addon-lifecycles.js');
let requests = 0;
global.fetch = async () => {
  requests += 1;
  return { json: async () => ({ description: 'Existing behavior', types: ['movie'] }) };
};

(async () => {
  const reviewed = { params: { data: { sulg: 'community-sample-0123456789ab', manifestUrl: 'https://example.com/manifest.json', description: 'Reviewed', types: ['series'] } } };
  await hooks.beforeCreate(reviewed);
  await hooks.beforeUpdate(reviewed);
  assert.equal(requests, 0);
  assert.equal(reviewed.params.data.description, 'Reviewed');
  const existing = { params: { data: { sulg: 'existing-addon', manifestUrl: 'https://example.com/manifest.json' } } };
  await hooks.beforeCreate(existing);
  assert.equal(requests, 1);
  assert.equal(existing.params.data.description, 'Existing behavior');
  console.log('CMS lifecycle: reviewed submissions skip refetch; existing behavior preserved.');
})().catch(error => { console.error(error); process.exitCode = 1; });
