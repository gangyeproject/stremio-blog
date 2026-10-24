module.exports = {
  async beforeCreate(event) {
    await fetchManifest(event);
  },
  async beforeUpdate(event) {
    await fetchManifest(event);
  },
};

async function fetchManifest(event) {
  const { data } = event.params;
  if (!data.manifestUrl) return;
  if (/^community-[a-z0-9-]+-[a-f0-9]{12}$/.test(data.sulg || '') &&
      typeof data.description === 'string' && Array.isArray(data.types)) return;

  try {
    const res = await fetch(data.manifestUrl);
    const manifest = await res.json();
    if (manifest.description) data.description = manifest.description;
    if (manifest.types) data.types = manifest.types;
  } catch (error) {
    console.log('Failed to fetch manifest:', error.message);
  }
}
