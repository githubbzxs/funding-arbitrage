import type { StrategyTemplate, StrategyTemplatePayload, StrategyTemplateUpdatePayload } from '../types/market';
import { request } from './http';

type GenericObject = Record<string, unknown>;

function asObject(input: unknown): GenericObject {
  if (typeof input === 'object' && input !== null) {
    return input as GenericObject;
  }
  return {};
}

function normalizeList(payload: unknown): GenericObject[] {
  if (Array.isArray(payload)) {
    return payload.filter((item): item is GenericObject => typeof item === 'object' && item !== null);
  }
  const root = asObject(payload);
  if (Array.isArray(root.items)) {
    return root.items.filter((item): item is GenericObject => typeof item === 'object' && item !== null);
  }
  return [];
}

function readString(record: GenericObject, key: string): string {
  const value = record[key];
  return typeof value === 'string' ? value : '';
}

function readNumberOrNull(record: GenericObject, key: string): number | null {
  const value = record[key];
  if (value === null || value === undefined || value === '') {
    return null;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function toTemplate(raw: GenericObject): StrategyTemplate {
  return {
    id: readString(raw, 'id'),
    name: readString(raw, 'name'),
    symbol: readString(raw, 'symbol'),
    long_exchange: readString(raw, 'long_exchange') as StrategyTemplate['long_exchange'],
    short_exchange: readString(raw, 'short_exchange') as StrategyTemplate['short_exchange'],
    mode: readString(raw, 'mode') as StrategyTemplate['mode'],
    quantity: readNumberOrNull(raw, 'quantity'),
    notional_usd: readNumberOrNull(raw, 'notional_usd'),
    leverage: readNumberOrNull(raw, 'leverage'),
    hold_hours: readNumberOrNull(raw, 'hold_hours'),
    note: (raw.note as string | null | undefined) ?? null,
    created_at: readString(raw, 'created_at'),
    updated_at: readString(raw, 'updated_at'),
  };
}

export async function fetchTemplates(limit = 500): Promise<StrategyTemplate[]> {
  const payload = await request<unknown>(`/api/templates?limit=${Math.max(1, Math.min(limit, 2000))}`);
  return normalizeList(payload).map(toTemplate);
}

export async function createTemplate(input: StrategyTemplatePayload): Promise<StrategyTemplate> {
  const payload = await request<unknown>('/api/templates', 'POST', input);
  return toTemplate(asObject(payload));
}

export async function updateTemplate(templateId: string, input: StrategyTemplateUpdatePayload): Promise<StrategyTemplate> {
  const payload = await request<unknown>(`/api/templates/${templateId}`, 'PUT', input);
  return toTemplate(asObject(payload));
}

export async function deleteTemplate(templateId: string): Promise<void> {
  await request(`/api/templates/${templateId}`, 'DELETE');
}
