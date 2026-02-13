export interface MarketRow {
  id: string;
  exchange: string;
  symbol: string;
  openInterestUsd: number;
  volume24hUsd: number;
  fundingRate1h: number;
  fundingRate8h: number;
  fundingRate1y: number;
  nextFundingTime: string;
  nextFundingRate: number;
  settlementInterval: string;
  maxLeverage: number;
  nominalApr: number;
  source: 'snapshot' | 'opportunity' | 'merged';
  longExchange?: string;
  shortExchange?: string;
  spreadRate1yNominal?: number;
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
