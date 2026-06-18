import { getAuthHeaders } from './authHeaders';

type SignedStreamResponse = {
  stream_url: string;
  token_expires_in: number;
};

async function postSignedStreamUrl(path: string): Promise<string> {
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to create signed stream URL: HTTP ${response.status}`);
  }

  const data = (await response.json()) as SignedStreamResponse;
  return data.stream_url;
}

export async function createAgentStreamUrl(runId: string, sinceSequence?: number): Promise<string> {
  const streamUrl = await postSignedStreamUrl(`/api/v1/agent/stream/${encodeURIComponent(runId)}/token`);
  if (sinceSequence === undefined || sinceSequence <= 0) return streamUrl;

  const url = new URL(streamUrl, window.location.origin);
  url.searchParams.set('since_sequence', String(sinceSequence));
  return `${url.pathname}${url.search}`;
}

export async function createMessagesStreamUrl(baseUrl: URL): Promise<string> {
  const tokenUrl = new URL('/api/v1/messages/stream/token', window.location.origin);
  baseUrl.searchParams.forEach((value, key) => tokenUrl.searchParams.set(key, value));
  return postSignedStreamUrl(`${tokenUrl.pathname}${tokenUrl.search}`);
}
