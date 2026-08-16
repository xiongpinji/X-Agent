import Constants from 'expo-constants';

export class MobileApiConfigurationError extends Error {
  constructor() {
    super('Mobile API base URL is not configured.');
    this.name = 'MobileApiConfigurationError';
  }
}

export function getApiBaseUrl(
  configuredValue = Constants.expoConfig?.extra?.apiBaseUrl
): string {
  const configured =
    typeof configuredValue === 'string' ? configuredValue.trim() : '';
  if (!configured) {
    throw new MobileApiConfigurationError();
  }

  let parsed: URL;
  try {
    parsed = new URL(configured);
  } catch {
    throw new MobileApiConfigurationError();
  }

  const localHttp =
    parsed.protocol === 'http:' &&
    ['localhost', '127.0.0.1', '::1'].includes(parsed.hostname);
  if (parsed.protocol !== 'https:' && !localHttp) {
    throw new MobileApiConfigurationError();
  }

  return configured.replace(/\/+$/, '');
}

export function buildApiUrl(path: string, configuredValue?: string): string {
  if (!path.startsWith('/')) {
    throw new MobileApiConfigurationError();
  }
  return `${getApiBaseUrl(configuredValue)}${path}`;
}

export function buildWebSocketUrl(path: string): string {
  const url = new URL(buildApiUrl(path));
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
}
