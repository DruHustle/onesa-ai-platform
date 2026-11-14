const invalidConfiguration = () => new Error('Invalid application origin configuration.');

/** @param {string | undefined} value */
function parseOrigin(value) {
  if (typeof value !== 'string' || !/^[a-z][a-z\d+.-]*:\/\/[^/?#\\\s@]+\/?$/i.test(value)) {
    throw invalidConfiguration();
  }
  let url;
  try {
    url = new URL(value);
  } catch {
    throw invalidConfiguration();
  }
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname ||
      url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw invalidConfiguration();
  }
  return url;
}

/** @param {string} hostname */
function isLoopback(hostname) {
  const host = hostname.toLowerCase().replace(/\.$/, '');
  return host === 'localhost' || host.endsWith('.localhost') ||
    /^127(?:\.\d{1,3}){3}$/.test(host) || host === '0.0.0.0' || host === '[::1]' || host === '[::]';
}

/**
 * Resolve a navigation origin using trusted build context and a pinned public default.
 * @param {{configured?: string, docsUrl?: string, environment?: string,
 *   staticHosting?: boolean, accessHosting?: boolean, publicOrigin?: string}} [options]
 * @returns {string}
 */
export function resolveApplicationOrigin(options = {}) {
  const docsOrigin = options.docsUrl ? parseOrigin(options.docsUrl) : undefined;
  const hosted = options.environment === 'staging' || options.environment === 'production' ||
    options.staticHosting === true || options.accessHosting === true ||
    (docsOrigin !== undefined && !isLoopback(docsOrigin.hostname));
  const url = parseOrigin(options.configured ||
    (hosted ? options.publicOrigin : 'http://localhost:3100'));
  if (hosted && (url.protocol !== 'https:' || isLoopback(url.hostname))) {
    throw invalidConfiguration();
  }
  return url.origin;
}
