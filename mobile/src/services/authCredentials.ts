import * as SecureStore from 'expo-secure-store';

export const ACCESS_TOKEN_KEY = 'auth_token';
export const REFRESH_TOKEN_KEY = 'refresh_token';
export const API_KEY_KEY = 'api_key';

export async function loadAuthHeaders(): Promise<Record<string, string>> {
  const accessToken = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
  if (accessToken) {
    return { Authorization: `Bearer ${accessToken}` };
  }

  const apiKey = await SecureStore.getItemAsync(API_KEY_KEY);
  return apiKey ? { 'x-api-key': apiKey } : {};
}
