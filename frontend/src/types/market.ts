export interface MarketRow {
  id: string;
  exchange: string;
  symbol: string;
  openInterestUsd: number;
  volume24hUsd: number;
  fundingRate1h: number | null;
  fundingRate8h: number | null;
  fundingRate1y: number | null;
  nextFundingTime: string;
  nextFundingRate: number | null;
  settlementInterval: string;
  maxLeverage: number | null;
  nominalApr: number | null;
  leveragedNominalApr: number | null;
  source: 'snapshot' | 'opportunity' | 'merged';
  longExchange?: string;
  shortExchange?: string;
  spreadRate1yNominal?: number;
  spreadRate8h?: number | null;
  spreadRate1h?: number | null;
  longMaxLeverage?: number | null;
  shortMaxLeverage?: number | null;
  maxUsableLeverage?: number | null;
  longRate8h?: number | null;
  shortRate8h?: number | null;
  longFundingRateRaw?: number | null;
  shortFundingRateRaw?: number | null;
  longNextFundingTime?: string;
  shortNextFundingTime?: string;
}

export interface FilterState {
  exchanges: string[];
}

export interface MarketFetchError {
  exchange: string;
  message: string;
}

export interface MarketMeta {
  fetchMs: number | null;
  cacheHit: boolean;
  exchangesOk: string[];
  exchangesFailed: string[];
}

export interface OpportunityLegInfo {
  exchange: string;
  openInterestUsd: number | null;
  volume24hUsd: number | null;
  fundingRateRaw: number | null;
  fundingRate1h: number | null;
  fundingRate8h: number | null;
  fundingRate1y: number | null;
  nextFundingTime: string;
  settlementInterval: string;
  maxLeverage: number | null;
  leveragedNominalApr: number | null;
}

export interface OpportunityPairRow {
  id: string;
  symbol: string;
  longExchange: string;
  shortExchange: string;
  longLeg: OpportunityLegInfo;
  shortLeg: OpportunityLegInfo;
  spreadRate1h: number | null;
  spreadRate8h: number | null;
  spreadRate1yNominal: number;
  leveragedSpreadRate1yNominal: number | null;
  rawOpportunity: MarketRow;
}

export type ExecutionAction = 'preview' | 'open' | 'close' | 'hedge' | 'emergency-close';

export interface ExchangeCredential {
  api_key: string;
  api_secret: string;
  passphrase?: string;
  testnet?: boolean;
}

export interface ExecutionPayload {
  [key: string]: unknown;
}

export interface ExecutionRequest {
  action: ExecutionAction;
  payload: ExecutionPayload;
}

export interface TradingRecord {
  id?: string | number;
  exchange?: string;
  symbol?: string;
  status?: string;
  [key: string]: unknown;
}
