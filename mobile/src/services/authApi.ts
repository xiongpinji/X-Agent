import { User } from '../types';
import { buildApiUrl } from './apiConfig';

interface BackendUser {
  id: string;
  email: string;
  display_name: string;
  role: string;
}

interface BackendLoginResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: BackendUser;
}

interface BackendRefreshResponse {
  access_token: string;
  expires_in: number;
}

export interface LoginResult {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user: User;
}

export interface RefreshResult {
  accessToken: string;
  expiresIn: number;
}

export class MobileAuthError extends Error {
  constructor() {
    super('Authentication request failed.');
    this.name = 'MobileAuthError';
  }
}

async function requestJson(path: string, init: RequestInit): Promise<unknown> {
  const response = await fetch(buildApiUrl(path), init);
  if (!response.ok) {
    throw new MobileAuthError();
  }
  return response.json();
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

export async function loginWithPassword(
  email: string,
  password: string
): Promise<LoginResult> {
  const raw = (await requestJson('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })) as Partial<BackendLoginResponse>;

  const user = raw.user as Partial<BackendUser> | undefined;
  if (
    !isNonEmptyString(raw.access_token) ||
    !isNonEmptyString(raw.refresh_token) ||
    typeof raw.expires_in !== 'number' ||
    !user ||
    !isNonEmptyString(user.id) ||
    !isNonEmptyString(user.email) ||
    !isNonEmptyString(user.display_name) ||
    !isNonEmptyString(user.role)
  ) {
    throw new MobileAuthError();
  }

  return {
    accessToken: raw.access_token,
    refreshToken: raw.refresh_token,
    expiresIn: raw.expires_in,
    user: {
      id: user.id,
      email: user.email,
      name: user.display_name,
      roles: [user.role],
      permissions: [],
    },
  };
}

export async function refreshWithToken(
  refreshToken: string
): Promise<RefreshResult> {
  const raw = (await requestJson('/api/v1/auth/refresh', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${refreshToken}`,
    },
  })) as Partial<BackendRefreshResponse>;

  if (
    !isNonEmptyString(raw.access_token) ||
    typeof raw.expires_in !== 'number'
  ) {
    throw new MobileAuthError();
  }

  return { accessToken: raw.access_token, expiresIn: raw.expires_in };
}
