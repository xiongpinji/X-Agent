export const AUTH_TOKEN_STORAGE_KEY = 'auth_token';
export const AUTH_REFRESH_TOKEN_STORAGE_KEY = 'auth_refresh_token';
export const AUTH_REDIRECT_STORAGE_KEY = 'auth_redirect_after_login';

let fetchInterceptorInstalled = false;

export function getStoredAuthToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  return token && token.trim() ? token : null;
}

export function getStoredRefreshToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  const token = localStorage.getItem(AUTH_REFRESH_TOKEN_STORAGE_KEY);
  return token && token.trim() ? token : null;
}

export function storeAuthSession(accessToken: string, refreshToken?: string | null): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, accessToken);
  if (refreshToken) {
    localStorage.setItem(AUTH_REFRESH_TOKEN_STORAGE_KEY, refreshToken);
  }
}

export function clearStoredAuthSession(): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  localStorage.removeItem(AUTH_REFRESH_TOKEN_STORAGE_KEY);
}

export function getAuthHeaders(getToken: () => string | null = getStoredAuthToken): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function redirectToLogin(): void {
  if (typeof window === 'undefined') return;
  const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (window.location.pathname === '/login') return;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(AUTH_REDIRECT_STORAGE_KEY, currentPath || '/');
  }
  const target = `/login?redirect=${encodeURIComponent(currentPath || '/')}`;
  window.location.assign(target);
}

export function consumeAuthRedirect(defaultPath = '/'): string {
  if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
    return defaultPath;
  }
  const queryRedirect = new URLSearchParams(window.location.search).get('redirect');
  const storedRedirect = localStorage.getItem(AUTH_REDIRECT_STORAGE_KEY);
  localStorage.removeItem(AUTH_REDIRECT_STORAGE_KEY);
  const target = queryRedirect || storedRedirect || defaultPath;
  if (!target.startsWith('/') || target.startsWith('//') || target.startsWith('/login')) {
    return defaultPath;
  }
  return target;
}

function isApiRequest(input: RequestInfo | URL): boolean {
  const url = typeof input === 'string' || input instanceof URL ? String(input) : input.url;
  if (url.startsWith('/api/')) return true;
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.origin === window.location.origin && parsed.pathname.startsWith('/api/');
  } catch {
    return false;
  }
}

export function installAuthenticatedFetch(): void {
  if (typeof window === 'undefined' || fetchInterceptorInstalled) return;
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const shouldHandleApiRequest = isApiRequest(input);
    const headers = new Headers(
      init.headers ?? (typeof input === 'string' || input instanceof URL ? undefined : input.headers),
    );
    const token = getStoredAuthToken();
    if (shouldHandleApiRequest && token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    const response = await originalFetch(input, { ...init, headers });
    if (shouldHandleApiRequest && response.status === 401) {
      clearStoredAuthSession();
      redirectToLogin();
    }
    return response;
  };
  fetchInterceptorInstalled = true;
}
