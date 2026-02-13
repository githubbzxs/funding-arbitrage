import type { ExchangeCredential } from '../types/market';
import { request } from './http';

type GenericObject = Record<string, unknown>;

export type CredentialStatus = {
  exchange: string;
  configured: boolean;
  api_key_masked?: string | null;
  has_passphrase?: boolean;
  testnet?: boolean | null;
  updated_at?: string | null;
};

function normalizeList(data: unknown): GenericObject[] {
  if (Array.isArray(data)) {
    return data.filter((item): item is GenericObject => typeof item === 'object' && item !== null);
  }
  if (typeof data === 'object' && data !== null) {
    const container = data as GenericObject;
    const candidate = container.items ?? container.data ?? container.credentials;
    if (Array.isArray(candidate)) {
      return candidate.filter((item): item is GenericObject => typeof item === 'object' && item !== null);
    }
  }
  return [];
}

function readString(record: GenericObject, key: string): string | null {
  const value = record[key];
  return typeof value === 'string' ? value : null;
}

function readBool(record: GenericObject, key: string): boolean | null {
  const value = record[key];
  return typeof value === 'boolean' ? value : null;
}

export async function fetchCredentialStatuses(): Promise<CredentialStatus[]> {
  const payload = await request<unknown>('/api/credentials');
  return normalizeList(payload).map((raw) => ({
    exchange: readString(raw, 'exchange') ?? '',
    configured: Boolean(raw.configured),
    api_key_masked: readString(raw, 'api_key_masked'),
    has_passphrase: Boolean(raw.has_passphrase),
    testnet: readBool(raw, 'testnet'),
    updated_at: readString(raw, 'updated_at')
  }));
}

export async function upsertCredential(exchange: string, credential: ExchangeCredential): Promise<unknown> {
  return request(`/api/credentials/${exchange}`, 'PUT', credential);
}

export async function deleteCredential(exchange: string): Promise<unknown> {
  return request(`/api/credentials/${exchange}`, 'DELETE');
}

