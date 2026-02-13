export type SupportedExchange = 'binance' | 'okx' | 'bybit' | 'bitget' | 'gateio';

export interface OpportunityBoardLeg {
  exchange: string;
  openInterestUsd: number | null;
  volume24hUsd: number | null;
  fundingRateRaw: number | null;
  fundingRate1h: number | null;
  fundingRate8h: number | null;
  fundingRate1y: number | null;
  nextFundingTime: string;
  settlementInterval: string;
  settlementIntervalHours: number | null;
  maxLeverage: number | null;
  leveragedNominalRate1y: number | null;
}

export interface OpportunityBoardRow {
  id: string;
  symbol: string;
  longExchange: string;
  shortExchange: string;
  longLeg: OpportunityBoardLeg;
  shortLeg: OpportunityBoardLeg;
  intervalMismatch: boolean;
  shorterIntervalSide: 'long' | 'short' | null;
  spreadRate1h: number | null;
  spreadRate8h: number | null;
  spreadRate1yNominal: number;
  leveragedSpreadRate1yNominal: number | null;
  maxUsableLeverage: number | null;
}

export interface MarginSimulation {
  marginUsd: number;
  leverage: number;
  notionalUsd: number;
  horizonHours: number;
  longIntervalHours: number;
  shortIntervalHours: number;
  longEvents: number;
  shortEvents: number;
  hedgedRate: number;
  singleSideRate: number;
  totalRate: number;
  expectedPnlUsd: number;
  intervalMismatch: boolean;
  shorterIntervalSide: 'long' | 'short' | null;
}

export interface MarketFetchError {
  exchange: string;
  message: string;
}

export interface BoardMeta {
  fetchMs: number | null;
  cacheHit: boolean;
  exchangesOk: string[];
  exchangesFailed: string[];
  exchangeSources: Record<string, string>;
  exchangeCounts: Record<string, number>;
}

export interface MarketBoardResult {
  asOf: string;
  total: number;
  rows: OpportunityBoardRow[];
  errors: MarketFetchError[];
  meta: BoardMeta | null;
}

export interface BoardQuery {
  limit?: number;
  minSpreadRate1yNominal?: number;
  forceRefresh?: boolean;
  exchanges?: string[];
  symbol?: string;
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
