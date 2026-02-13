import type { MarketRow, TradingRecord } from '../types/market';
import { toNumber } from '../utils/format';
import { request } from './http';

type GenericObject = Record<string, unknown>;

function readString(record: GenericObject, keys: string[], fallback = ''): string {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return fallback;
}

function readNumber(record: GenericObject, keys: string[], fallback = 0): number {
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

function normalizeList(data: unknown): GenericObject[] {
  if (Array.isArray(data)) {
    return data.filter((item): item is GenericObject => typeof item === 'object' && item !== null);
  }

  if (typeof data === 'object' && data !== null) {
    const container = data as GenericObject;
    const candidateKeys = ['data', 'items', 'rows', 'result', 'snapshots', 'opportunities'];
    for (const key of candidateKeys) {
      const value = container[key];
      if (Array.isArray(value)) {
        return value.filter((item): item is GenericObject => typeof item === 'object' && item !== null);
      }
    }
  }

  return [];
}

function hourLabel(hours: number): string {
  if (!Number.isFinite(hours) || hours <= 0) {
    return '-';
  }
  const normalized = Math.round(hours * 100) / 100;
  if (Number.isInteger(normalized)) {
    return `${normalized.toFixed(0)}h`;
  }
  return `${normalized}h`;
}

function buildSnapshotRow(raw: GenericObject): MarketRow {
  const intervalHours = readNumber(raw, ['funding_interval_hours', 'fundingIntervalHours', 'intervalHours'], 8);
  const fundingRaw = readNumber(raw, ['funding_rate_raw', 'fundingRateRaw'], 0);
  const rate1h = readNumber(raw, ['rate_1h', 'rate1h'], intervalHours > 0 ? fundingRaw / intervalHours : 0);
  const rate8h = readNumber(raw, ['rate_8h', 'rate8h'], rate1h * 8);
  const rate1y = readNumber(raw, ['rate_1y', 'rate1y'], rate1h * 24 * 365);
  const nominal = readNumber(raw, ['nominal_rate_1y', 'nominalRate1y'], rate1y * readNumber(raw, ['max_leverage'], 1));

  return {
    id: `${readString(raw, ['exchange'])}-${readString(raw, ['symbol'])}`,
    exchange: readString(raw, ['exchange'], '-'),
    symbol: readString(raw, ['symbol'], '-'),
    openInterestUsd: readNumber(raw, ['oi_usd', 'oiUsd'], 0),
    volume24hUsd: readNumber(raw, ['vol24h_usd', 'vol24hUsd'], 0),
    fundingRate1h: rate1h,
    fundingRate8h: rate8h,
    fundingRate1y: rate1y,
    nextFundingTime: readString(raw, ['next_funding_time', 'nextFundingTime'], ''),
    nextFundingRate: fundingRaw,
    settlementInterval: hourLabel(intervalHours),
    maxLeverage: readNumber(raw, ['max_leverage', 'maxLeverage'], 0),
    nominalApr: nominal,
    source: 'snapshot'
  };
}

function buildOpportunityRow(raw: GenericObject): MarketRow {
  const longRate8h = readNumber(raw, ['long_rate_8h', 'longRate8h'], 0);
  const shortRate8h = readNumber(raw, ['short_rate_8h', 'shortRate8h'], 0);
  const spreadNominal = readNumber(raw, ['spread_rate_1y_nominal', 'spreadRate1yNominal'], 0);
  const longExchange = readString(raw, ['long_exchange', 'longExchange'], '');
  const shortExchange = readString(raw, ['short_exchange', 'shortExchange'], '');

  return {
    id: `opportunity-${longExchange}-${shortExchange}-${readString(raw, ['symbol'])}`,
    exchange: `${longExchange}/${shortExchange}`,
    symbol: readString(raw, ['symbol'], '-'),
    openInterestUsd: 0,
    volume24hUsd: 0,
    fundingRate1h: (shortRate8h - longRate8h) / 8,
    fundingRate8h: shortRate8h - longRate8h,
    fundingRate1y: spreadNominal,
    nextFundingTime:
      readString(raw, ['long_next_funding_time', 'longNextFundingTime']) ||
      readString(raw, ['short_next_funding_time', 'shortNextFundingTime']),
    nextFundingRate:
      readNumber(raw, ['short_funding_rate_raw', 'shortFundingRateRaw'], 0) -
      readNumber(raw, ['long_funding_rate_raw', 'longFundingRateRaw'], 0),
    settlementInterval: '8h',
    maxLeverage: 0,
    nominalApr: spreadNominal,
    source: 'opportunity',
    longExchange,
    shortExchange,
    spreadRate1yNominal: spreadNominal
  };
}

export async function fetchSnapshots(): Promise<MarketRow[]> {
  const payload = await request<unknown>('/api/market/snapshots');
  return normalizeList(payload).map(buildSnapshotRow);
}

export async function fetchOpportunities(): Promise<MarketRow[]> {
  const payload = await request<unknown>('/api/opportunities');
  return normalizeList(payload).map(buildOpportunityRow);
}

export async function fetchPositions(): Promise<TradingRecord[]> {
  const payload = await request<unknown>('/api/positions');
  return normalizeList(payload) as TradingRecord[];
}

export async function fetchOrders(): Promise<TradingRecord[]> {
  const payload = await request<unknown>('/api/orders');
  return normalizeList(payload) as TradingRecord[];
}
