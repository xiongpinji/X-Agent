export const AUTH_TOKEN_STORAGE_KEY = 'auth_token';

export function getStoredAuthToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  return token && token.trim() ? token : null;
}

export function getAuthHeaders(getToken: () => string | null = getStoredAuthToken): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
