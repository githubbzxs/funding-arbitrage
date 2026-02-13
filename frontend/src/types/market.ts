export type SupportedExchange = 'binance' | 'okx' | 'bybit' | 'bitget' | 'gateio';
export type OpportunityLegSide = 'long' | 'short';
export type SettlementEventKind = 'hedged' | 'single_side' | 'unknown';

export interface SettlementEventPreview {
  id: string;
  eventTime: string;
  kind: SettlementEventKind;
  side: OpportunityLegSide | null;
  amountRate: number | null;
  hedgedRate: number | null;
  singleSideRate: number | null;
  longRateRaw: number | null;
  shortRateRaw: number | null;
  summary: string;
}

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
  nextCycleScore: number | null;
  nextCycleScoreUnleveraged: number | null;
  nextSettlementTime: string;
  settlementEventsPreview: SettlementEventPreview[];
  singleSideEventCount: number;
  maxUsableLeverage: number | null;
}

export interface MarginSimulationEvent {
  id: string;
  eventTime: string;
  kind: SettlementEventKind;
  side: OpportunityLegSide | null;
  amountRate: number;
  pnlUsd: number;
  summary: string;
}

export interface MarginSimulation {
  marginUsd: number;
  leverage: number;
  notionalUsd: number;
  eventCount: number;
  singleSideEventCount: number;
  hedgedRate: number;
  singleSideRate: number;
  totalRate: number;
  expectedPnlUsd: number;
  intervalMismatch: boolean;
  shorterIntervalSide: 'long' | 'short' | null;
  nextSettlementTime: string;
  windowStartTime: string;
  windowEndTime: string;
  events: MarginSimulationEvent[];
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
  minNextCycleScore?: number;
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
