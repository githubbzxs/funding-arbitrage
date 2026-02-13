const API_BASE = import.meta.env.VITE_API_BASE ?? '';

type RequestMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';

export async function request<T>(path: string, method: RequestMethod = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json'
    },
    body: body === undefined ? undefined : JSON.stringify(body)
  });

  const contentType = response.headers.get('content-type') ?? '';
  const payload: unknown = contentType.includes('application/json') ? await response.json() : await response.text();

  if (!response.ok) {
    const message = typeof payload === 'string' ? payload : JSON.stringify(payload);
    throw new Error(message || `请求失败：${response.status}`);
  }

  return payload as T;
}
