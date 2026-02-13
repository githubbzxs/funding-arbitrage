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

function readOptionalNumber(record: GenericObject, keys: string[]): number | null {
  for (const key of keys) {
    if (!(key in record)) {
      continue;
    }
    const parsed = toNumber(record[key], Number.NaN);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
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
  const fundingRaw = readOptionalNumber(raw, ['funding_rate_raw', 'fundingRateRaw']);

  const rate1hApi = readOptionalNumber(raw, ['rate_1h', 'rate1h']);
  const rate1h = rate1hApi ?? (fundingRaw !== null && intervalHours > 0 ? fundingRaw / intervalHours : null);

  const rate8hApi = readOptionalNumber(raw, ['rate_8h', 'rate8h']);
  const rate8h = rate8hApi ?? (rate1h !== null ? rate1h * 8 : null);

  const rate1yApi = readOptionalNumber(raw, ['rate_1y', 'rate1y']);
  const rate1y = rate1yApi ?? (rate1h !== null ? rate1h * 24 * 365 : null);

  const maxLeverage = readOptionalNumber(raw, ['max_leverage', 'maxLeverage']);
  const nominalApi = readOptionalNumber(raw, ['nominal_rate_1y', 'nominalRate1y']);
  const nominal = nominalApi ?? (rate1h !== null ? rate1h * 24 * 365 : null);
  const leveragedNominalApi = readOptionalNumber(raw, ['leveraged_nominal_rate_1y', 'leveragedNominalRate1y']);
  const leveragedNominal =
    leveragedNominalApi ?? (nominal !== null && maxLeverage !== null ? nominal * maxLeverage : null);

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
    maxLeverage,
    nominalApr: nominal,
    leveragedNominalApr: leveragedNominal,
    maxUsableLeverage: maxLeverage,
    source: 'snapshot'
  };
}

function buildOpportunityRow(raw: GenericObject): MarketRow {
  const longRate8h = readOptionalNumber(raw, ['long_rate_8h', 'longRate8h']);
  const shortRate8h = readOptionalNumber(raw, ['short_rate_8h', 'shortRate8h']);
  const spreadNominal = readNumber(raw, ['spread_rate_1y_nominal', 'spreadRate1yNominal'], 0);
  const longExchange = readString(raw, ['long_exchange', 'longExchange'], '');
  const shortExchange = readString(raw, ['short_exchange', 'shortExchange'], '');
  const longMaxLeverage = readOptionalNumber(raw, ['long_max_leverage', 'longMaxLeverage']);
  const shortMaxLeverage = readOptionalNumber(raw, ['short_max_leverage', 'shortMaxLeverage']);
  const maxUsableApi = readOptionalNumber(raw, ['max_usable_leverage', 'maxUsableLeverage']);
  const maxUsable =
    maxUsableApi ??
    (longMaxLeverage !== null && shortMaxLeverage !== null ? Math.min(longMaxLeverage, shortMaxLeverage) : null);
  const leveragedSpreadApi = readOptionalNumber(raw, ['leveraged_spread_rate_1y_nominal', 'leveragedSpreadRate1yNominal']);
  const leveragedSpread = leveragedSpreadApi ?? (maxUsable !== null ? spreadNominal * maxUsable : null);

  const rate8h = longRate8h !== null && shortRate8h !== null ? shortRate8h - longRate8h : null;
  const rate1h = rate8h !== null ? rate8h / 8 : null;
  const shortFundingRaw = readOptionalNumber(raw, ['short_funding_rate_raw', 'shortFundingRateRaw']);
  const longFundingRaw = readOptionalNumber(raw, ['long_funding_rate_raw', 'longFundingRateRaw']);
  const nextFundingRate = shortFundingRaw !== null && longFundingRaw !== null ? shortFundingRaw - longFundingRaw : null;

  return {
    id: `opportunity-${longExchange}-${shortExchange}-${readString(raw, ['symbol'])}`,
    exchange: `${longExchange}/${shortExchange}`,
    symbol: readString(raw, ['symbol'], '-'),
    openInterestUsd: 0,
    volume24hUsd: 0,
    fundingRate1h: rate1h,
    fundingRate8h: rate8h,
    fundingRate1y: spreadNominal,
    nextFundingTime:
      readString(raw, ['long_next_funding_time', 'longNextFundingTime']) ||
      readString(raw, ['short_next_funding_time', 'shortNextFundingTime']),
    nextFundingRate,
    settlementInterval: '8h',
    maxLeverage: maxUsable,
    nominalApr: spreadNominal,
    leveragedNominalApr: leveragedSpread,
    source: 'opportunity',
    longExchange,
    shortExchange,
    spreadRate1yNominal: spreadNominal,
    longMaxLeverage,
    shortMaxLeverage,
    maxUsableLeverage: maxUsable
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
