import type { OrderRecord, PositionRecord, RiskEventRecord } from '../types/market';
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

function readNumber(record: GenericObject, key: string): number {
  const value = record[key];
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return 0;
}

function readBoolean(record: GenericObject, key: string): boolean {
  const value = record[key];
  if (typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'number') {
    return value !== 0;
  }
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (normalized === 'true' || normalized === '1') {
      return true;
    }
    if (normalized === 'false' || normalized === '0') {
      return false;
    }
  }
  return false;
}

function readObject(record: GenericObject, key: string): Record<string, unknown> {
  const value = record[key];
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function toPosition(raw: GenericObject): PositionRecord {
  return {
    id: readString(raw, 'id'),
    symbol: readString(raw, 'symbol'),
    long_exchange: readString(raw, 'long_exchange'),
    short_exchange: readString(raw, 'short_exchange'),
    long_qty: readNumber(raw, 'long_qty'),
    short_qty: readNumber(raw, 'short_qty'),
    mode: readString(raw, 'mode'),
    status: readString(raw, 'status'),
    entry_spread_rate: raw.entry_spread_rate as number | null | undefined,
    opened_at: readString(raw, 'opened_at'),
    closed_at: (raw.closed_at as string | null | undefined) ?? null,
    created_at: readString(raw, 'created_at'),
    updated_at: readString(raw, 'updated_at'),
    extra: readObject(raw, 'extra'),
  };
}

function toOrder(raw: GenericObject): OrderRecord {
  return {
    id: readString(raw, 'id'),
    position_id: (raw.position_id as string | null | undefined) ?? null,
    action: readString(raw, 'action'),
    mode: readString(raw, 'mode'),
    status: readString(raw, 'status'),
    exchange: readString(raw, 'exchange'),
    symbol: readString(raw, 'symbol'),
    side: readString(raw, 'side'),
    quantity: readNumber(raw, 'quantity'),
    filled_qty: (raw.filled_qty as number | null | undefined) ?? null,
    avg_price: (raw.avg_price as number | null | undefined) ?? null,
    exchange_order_id: (raw.exchange_order_id as string | null | undefined) ?? null,
    note: (raw.note as string | null | undefined) ?? null,
    created_at: readString(raw, 'created_at'),
    updated_at: readString(raw, 'updated_at'),
    extra: readObject(raw, 'extra'),
  };
}

function toRiskEvent(raw: GenericObject): RiskEventRecord {
  return {
    id: readString(raw, 'id'),
    event_type: readString(raw, 'event_type'),
    severity: readString(raw, 'severity'),
    message: readString(raw, 'message'),
    context: readObject(raw, 'context'),
    resolved: readBoolean(raw, 'resolved'),
    created_at: readString(raw, 'created_at'),
    updated_at: readString(raw, 'updated_at'),
  };
}

export async function fetchPositions(limit = 200): Promise<PositionRecord[]> {
  const payload = await request<unknown>(`/api/positions?limit=${Math.max(1, Math.min(limit, 2000))}`);
  return normalizeList(payload).map(toPosition);
}

export async function fetchOrders(limit = 500): Promise<OrderRecord[]> {
  const payload = await request<unknown>(`/api/orders?limit=${Math.max(1, Math.min(limit, 5000))}`);
  return normalizeList(payload).map(toOrder);
}

export async function fetchRiskEvents(filters?: {
  limit?: number;
  resolved?: boolean;
  severity?: string;
}): Promise<RiskEventRecord[]> {
  const params = new URLSearchParams();
  params.set('limit', String(Math.max(1, Math.min(filters?.limit ?? 200, 2000))));
  if (typeof filters?.resolved === 'boolean') {
    params.set('resolved', filters.resolved ? 'true' : 'false');
  }
  if (filters?.severity) {
    params.set('severity', filters.severity);
  }
  const payload = await request<unknown>(`/api/risk-events?${params.toString()}`);
  return normalizeList(payload).map(toRiskEvent);
}

export async function resolveRiskEvent(eventId: string): Promise<RiskEventRecord> {
  const payload = await request<unknown>(`/api/risk-events/${eventId}/resolve`, 'POST');
  return toRiskEvent(asObject(payload));
}
