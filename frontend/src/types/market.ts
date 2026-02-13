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
  longMaxLeverage?: number | null;
  shortMaxLeverage?: number | null;
  maxUsableLeverage?: number | null;
}

export interface FilterState {
  oiThreshold: number;
  volumeThreshold: number;
  intervals: string[];
  exchanges: string[];
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
