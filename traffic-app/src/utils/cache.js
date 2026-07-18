/**
 * Read a fresh entry and promote it to the most-recently-used position.
 *
 * @template T
 * @param {Map<string, { data: T, timestamp: number }>} cache
 * @param {string} key
 * @param {number} ttl
 * @returns {T | null}
 */
export function getCachedEntry(cache, key, ttl) {
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.timestamp > ttl) {
    cache.delete(key);
    return null;
  }

  cache.delete(key);
  cache.set(key, entry);
  return entry.data;
}

/**
 * Store an entry and evict the least-recently-used entries over the limit.
 *
 * @template T
 * @param {Map<string, { data: T, timestamp: number }>} cache
 * @param {string} key
 * @param {T} data
 * @param {number} maxEntries
 */
export function setCachedEntry(cache, key, data, maxEntries) {
  cache.delete(key);
  cache.set(key, { data, timestamp: Date.now() });
  while (cache.size > maxEntries) {
    const oldestKey = cache.keys().next().value;
    if (oldestKey === undefined) return;
    cache.delete(oldestKey);
  }
}
