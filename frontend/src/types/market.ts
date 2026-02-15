export type SupportedExchange = 'binance' | 'okx' | 'bybit' | 'bitget' | 'gateio';

export type ExecutionAction = 'preview' | 'open' | 'close' | 'hedge' | 'emergency-close';
export type ExecutionMode = 'auto';

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

export interface PositionRecord {
  id: string;
  symbol: string;
  long_exchange: string;
  short_exchange: string;
  long_qty: number;
  short_qty: number;
  mode: string;
  status: string;
  entry_spread_rate?: number | null;
  opened_at: string;
  closed_at?: string | null;
  created_at: string;
  updated_at: string;
  extra?: Record<string, unknown>;
}

export interface OrderRecord {
  id: string;
  position_id?: string | null;
  action: string;
  mode: string;
  status: string;
  exchange: string;
  symbol: string;
  side: string;
  quantity: number;
  filled_qty?: number | null;
  avg_price?: number | null;
  exchange_order_id?: string | null;
  note?: string | null;
  created_at: string;
  updated_at: string;
  extra?: Record<string, unknown>;
}

export interface RiskEventRecord {
  id: string;
  event_type: string;
  severity: string;
  message: string;
  context: Record<string, unknown>;
  resolved: boolean;
  created_at: string;
  updated_at: string;
}

export interface StrategyTemplate {
  id: string;
  name: string;
  symbol: string;
  long_exchange: SupportedExchange;
  short_exchange: SupportedExchange;
  notional_usd: number | null;
  leverage: number | null;
  hold_hours: number | null;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface StrategyTemplatePayload {
  name: string;
  symbol: string;
  long_exchange: SupportedExchange;
  short_exchange: SupportedExchange;
  notional_usd?: number | null;
  leverage?: number | null;
  hold_hours?: number | null;
  note?: string | null;
}

export interface StrategyTemplateUpdatePayload {
  name?: string;
  symbol?: string;
  long_exchange?: SupportedExchange;
  short_exchange?: SupportedExchange;
  notional_usd?: number | null;
  leverage?: number | null;
  hold_hours?: number | null;
  note?: string | null;
}
