const categoryDefinitions = [
  ['movies', 'Movies', ['movie', 'movies']],
  ['series', 'TV Shows', ['series', 'tv shows', 'tv show']],
  ['anime', 'Anime', ['anime']],
  ['asian-drama', 'Asian Drama', ['asian drama']],
  ['bollywood', 'Bollywood', ['bollywood']],
  ['live-tv', 'Live TV', ['tv', 'live tv']],
  ['subtitles', 'Subtitles', ['subtitles', 'subtitle']],
  ['music-radio', 'Music & Radio', ['music', 'radio', 'radios']],
  ['metadata', 'Catalogs & Metadata', ['metadata', 'catalog', 'catalogs']],
  ['tracking', 'Tracking', ['tracking']],
  ['http-streams', 'HTTP Streams', ['http streams']],
  ['torrents', 'Torrents', ['torrent', 'torrents']],
  ['debrid', 'Debrid Support', ['debrid', 'debrid support']],
  ['usenet', 'Usenet', ['usenet']],
];

export function normalizeSearch(value = '') {
  return String(value).normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase().replace(/\s+/g, ' ').trim();
}

export function getAddonCategories(addon) {
  const types = (Array.isArray(addon.types) ? addon.types : [])
    .filter(type => typeof type === 'string')
    .flatMap(type => type.split(',').map(normalizeSearch));
  const categories = categoryDefinitions
    .filter(([, , aliases]) => aliases.some(alias => types.includes(alias)))
    .map(([id]) => id);
  return categories.length ? categories : ['other'];
}

export function getCategoryOptions(addons) {
  const counts = new Map();
  for (const addon of addons) {
    for (const category of getAddonCategories(addon)) {
      counts.set(category, (counts.get(category) || 0) + 1);
    }
  }
  return [...categoryDefinitions, ['other', 'Other / Uncategorized', []]]
    .filter(([id]) => counts.has(id))
    .map(([id, label]) => ({ id, label, count: counts.get(id) }));
}

export function getAddonSearchText(addon) {
  const categories = getAddonCategories(addon);
  return normalizeSearch([
    addon.title, addon.sulg, addon.summary, addon.description,
    ...categoryDefinitions.filter(([id]) => categories.includes(id)).map(([, label]) => label),
  ].filter(value => typeof value === 'string').join(' '));
}

export function matchesAddon(searchText, categories, query, category) {
  return (!category || categories.includes(category)) &&
    normalizeSearch(query).split(' ').filter(Boolean).every(term => searchText.includes(term));
}
