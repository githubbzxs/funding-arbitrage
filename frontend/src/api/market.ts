import type { BoardMeta, BoardQuery, MarketBoardResult, MarketFetchError, OpportunityBoardLeg, OpportunityBoardRow, TradingRecord } from '../types/market';
import { toNumber } from '../utils/format';
import { request } from './http';

type GenericObject = Record<string, unknown>;

function asObject(input: unknown): GenericObject {
  if (typeof input === 'object' && input !== null) {
    return input as GenericObject;
  }
  return {};
}

function readString(record: GenericObject, keys: string[], fallback = ''): string {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return fallback;
}

function readBoolean(record: GenericObject, keys: string[], fallback = false): boolean {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'boolean') {
      return value;
    }
    if (typeof value === 'number') {
      return value !== 0;
    }
    if (typeof value === 'string') {
      const normalized = value.trim().toLowerCase();
      if (!normalized) {
        continue;
      }
      if (normalized === 'true' || normalized === '1' || normalized === 'yes') {
        return true;
      }
      if (normalized === 'false' || normalized === '0' || normalized === 'no') {
        return false;
      }
    }
  }
  return fallback;
}

function readNumber(record: GenericObject, keys: string[], fallback = Number.NaN): number {
  for (const key of keys) {
    if (!(key in record)) {
      continue;
    }
    const parsed = toNumber(record[key], Number.NaN);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return fallback;
}

function readOptionalNumber(record: GenericObject, keys: string[]): number | null {
  const parsed = readNumber(record, keys, Number.NaN);
  return Number.isFinite(parsed) ? parsed : null;
}

function readArray(record: GenericObject, keys: string[]): GenericObject[] {
  for (const key of keys) {
    const value = record[key];
    if (Array.isArray(value)) {
      return value.filter((item): item is GenericObject => typeof item === 'object' && item !== null);
    }
  }
  return [];
}

function readStringRecord(input: unknown): Record<string, string> {
  const source = asObject(input);
  const output: Record<string, string> = {};
  Object.entries(source).forEach(([key, value]) => {
    if (typeof value === 'string' && value.trim()) {
      output[key] = value.trim();
    }
  });
  return output;
}

function readNumberRecord(input: unknown): Record<string, number> {
  const source = asObject(input);
  const output: Record<string, number> = {};
  Object.entries(source).forEach(([key, value]) => {
    const parsed = toNumber(value, Number.NaN);
    if (Number.isFinite(parsed)) {
      output[key] = parsed;
    }
  });
  return output;
}

function readStringList(input: unknown): string[] {
  if (!Array.isArray(input)) {
    return [];
  }
  return input.filter((item): item is string => typeof item === 'string' && item.trim().length > 0).map((item) => item.trim());
}

function formatIntervalHours(hours: number): string {
  if (!Number.isFinite(hours) || hours <= 0) {
    return '-';
  }
  if (Math.abs(hours - Math.round(hours)) < 1e-9) {
    return `${Math.round(hours)}h`;
  }
  return `${hours.toFixed(2).replace(/\.?0+$/, '')}h`;
}

function toLeg(raw: GenericObject): OpportunityBoardLeg {
  const intervalHours = readOptionalNumber(raw, ['settlement_interval_hours', 'settlementIntervalHours', 'funding_interval_hours', 'fundingIntervalHours']);
  const intervalText = intervalHours !== null ? formatIntervalHours(intervalHours) : readString(raw, ['settlement_interval', 'settlementInterval'], '-');
  return {
    exchange: readString(raw, ['exchange'], '-'),
    openInterestUsd: readOptionalNumber(raw, ['open_interest_usd', 'openInterestUsd']),
    volume24hUsd: readOptionalNumber(raw, ['volume24h_usd', 'volume24hUsd']),
    fundingRateRaw: readOptionalNumber(raw, ['funding_rate_raw', 'fundingRateRaw']),
    fundingRate1h: readOptionalNumber(raw, ['rate_1h', 'rate1h']),
    fundingRate8h: readOptionalNumber(raw, ['rate_8h', 'rate8h']),
    fundingRate1y: readOptionalNumber(raw, ['rate_1y', 'rate1y']),
    nextFundingTime: readString(raw, ['next_funding_time', 'nextFundingTime']),
    settlementInterval: intervalText,
    settlementIntervalHours: intervalHours,
    maxLeverage: readOptionalNumber(raw, ['max_leverage', 'maxLeverage']),
    leveragedNominalRate1y: readOptionalNumber(raw, ['leveraged_nominal_rate_1y', 'leveragedNominalRate1y'])
  };
}

function toRow(raw: GenericObject): OpportunityBoardRow {
  const longExchange = readString(raw, ['long_exchange', 'longExchange'], '');
  const shortExchange = readString(raw, ['short_exchange', 'shortExchange'], '');
  const longLeg = toLeg(asObject(raw.long_leg));
  const shortLeg = toLeg(asObject(raw.short_leg));
  if (!longLeg.exchange || longLeg.exchange === '-') {
    longLeg.exchange = longExchange || '-';
  }
  if (!shortLeg.exchange || shortLeg.exchange === '-') {
    shortLeg.exchange = shortExchange || '-';
  }
  const spreadRate1yNominal = readNumber(raw, ['spread_rate_1y_nominal', 'spreadRate1yNominal'], 0);
  const shorterIntervalSideRaw = readString(raw, ['shorter_interval_side', 'shorterIntervalSide']);
  const shorterIntervalSide = shorterIntervalSideRaw === 'long' || shorterIntervalSideRaw === 'short' ? shorterIntervalSideRaw : null;
  return {
    id: readString(raw, ['id'], `${readString(raw, ['symbol'], '-')}-${longExchange || longLeg.exchange}-${shortExchange || shortLeg.exchange}`),
    symbol: readString(raw, ['symbol'], '-'),
    longExchange: longExchange || longLeg.exchange,
    shortExchange: shortExchange || shortLeg.exchange,
    longLeg,
    shortLeg,
    intervalMismatch: readBoolean(raw, ['interval_mismatch', 'intervalMismatch']),
    shorterIntervalSide,
    spreadRate1h: readOptionalNumber(raw, ['spread_rate_1h', 'spreadRate1h']),
    spreadRate8h: readOptionalNumber(raw, ['spread_rate_8h', 'spreadRate8h']),
    spreadRate1yNominal,
    leveragedSpreadRate1yNominal: readOptionalNumber(raw, ['leveraged_spread_rate_1y_nominal', 'leveragedSpreadRate1yNominal']),
    maxUsableLeverage: readOptionalNumber(raw, ['max_usable_leverage', 'maxUsableLeverage'])
  };
}

function toMeta(raw: unknown): BoardMeta | null {
  const input = asObject(raw);
  if (Object.keys(input).length === 0) {
    return null;
  }
  return {
    fetchMs: readOptionalNumber(input, ['fetch_ms', 'fetchMs']),
    cacheHit: Boolean(input.cache_hit ?? input.cacheHit),
    exchangesOk: readStringList(input.exchanges_ok ?? input.exchangesOk),
    exchangesFailed: readStringList(input.exchanges_failed ?? input.exchangesFailed),
    exchangeSources: readStringRecord(input.exchange_sources ?? input.exchangeSources),
    exchangeCounts: readNumberRecord(input.exchange_counts ?? input.exchangeCounts)
  };
}

function toErrors(raw: unknown): MarketFetchError[] {
  return readArray(asObject({ errors: raw }), ['errors'])
    .map((item) => ({
      exchange: readString(item, ['exchange'], ''),
      message: readString(item, ['message'], '未知错误')
    }))
    .filter((item) => item.exchange.length > 0 || item.message.length > 0);
}

function buildBoardQueryString(query?: BoardQuery): string {
  if (!query) {
    return '';
  }
  const params = new URLSearchParams();
  if (query.limit && query.limit > 0) {
    params.set('limit', String(query.limit));
  }
  if (typeof query.minSpreadRate1yNominal === 'number') {
    params.set('min_spread_rate_1y_nominal', String(query.minSpreadRate1yNominal));
  }
  if (query.forceRefresh) {
    params.set('force_refresh', '1');
  }
  if (query.exchanges && query.exchanges.length > 0) {
    query.exchanges.forEach((exchange) => {
      if (exchange.trim()) {
        params.append('exchanges', exchange.trim().toLowerCase());
      }
    });
  }
  if (query.symbol && query.symbol.trim()) {
    params.set('symbol', query.symbol.trim().toUpperCase());
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : '';
}

export async function fetchBoard(query?: BoardQuery): Promise<MarketBoardResult> {
  const payload = await request<unknown>(`/api/market/board${buildBoardQueryString(query)}`);
  const root = asObject(payload);
  const rows = readArray(root, ['rows']).map(toRow);
  return {
    asOf: readString(root, ['as_of', 'asOf']),
    total: readNumber(root, ['total'], rows.length),
    rows,
    errors: toErrors(root.errors),
    meta: toMeta(root.meta)
  };
}

function normalizeList(data: unknown): GenericObject[] {
  if (Array.isArray(data)) {
    return data.filter((item): item is GenericObject => typeof item === 'object' && item !== null);
  }
  const root = asObject(data);
  const list = root.items;
  if (Array.isArray(list)) {
    return list.filter((item): item is GenericObject => typeof item === 'object' && item !== null);
  }
  return [];
}

export async function fetchPositions(): Promise<TradingRecord[]> {
  const payload = await request<unknown>('/api/positions');
  return normalizeList(payload) as TradingRecord[];
}

export async function fetchOrders(): Promise<TradingRecord[]> {
  const payload = await request<unknown>('/api/orders');
  return normalizeList(payload) as TradingRecord[];
}
