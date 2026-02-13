const SUPPORTED_EXCHANGES = ['binance', 'okx', 'bybit', 'bitget', 'gateio'] as const;

export type SupportedExchange = (typeof SUPPORTED_EXCHANGES)[number];

export type TradeLeg = 'long' | 'short';

export type PairTradeTarget = {
  exchange: SupportedExchange;
  leg: TradeLeg;
  url: string;
};

export type PairTradeTargetsResult = {
  symbol: string;
  targets: PairTradeTarget[];
  invalidExchanges: string[];
  failedExchanges: SupportedExchange[];
  duplicateExchanges: SupportedExchange[];
};

function normalizeSymbol(symbol: string): string {
  return symbol.toUpperCase().replace(/[^A-Z0-9]/g, '');
}

function normalizeExchange(exchange: string): string {
  return exchange.trim().toLowerCase();
}

function resolveBaseAsset(symbol: string): string {
  const normalized = normalizeSymbol(symbol);
  if (normalized.endsWith('USDT')) {
    return normalized.slice(0, -4);
  }
  return normalized;
}

function isSupportedExchange(exchange: string): exchange is SupportedExchange {
  return (SUPPORTED_EXCHANGES as readonly string[]).includes(exchange);
}

export function buildExchangeTradeUrl(exchange: string, symbol: string): string | null {
  const normalizedExchange = normalizeExchange(exchange);
  if (!isSupportedExchange(normalizedExchange)) {
    return null;
  }

  const normalizedSymbol = normalizeSymbol(symbol);
  if (!normalizedSymbol) {
    return null;
  }
  const baseAsset = resolveBaseAsset(normalizedSymbol);
  if (!baseAsset) {
    return null;
  }

  if (normalizedExchange === 'binance') {
    return `https://www.binance.com/en/futures/${normalizedSymbol}`;
  }
  if (normalizedExchange === 'okx') {
    return `https://www.okx.com/trade-swap/${baseAsset}-usdt-swap`;
  }
  if (normalizedExchange === 'bybit') {
    return `https://www.bybit.com/trade/usdt/${normalizedSymbol}`;
  }
  if (normalizedExchange === 'bitget') {
    return `https://www.bitget.com/futures/usdt/${normalizedSymbol}`;
  }
  return `https://www.gate.com/futures/USDT/${baseAsset}_USDT`;
}

export function buildPairTradeTargets(
  longExchange: string,
  shortExchange: string,
  symbol: string,
): PairTradeTargetsResult {
  const normalizedSymbol = normalizeSymbol(symbol);
  const entries: Array<{ leg: TradeLeg; exchange: string }> = [
    { leg: 'long', exchange: normalizeExchange(longExchange) },
    { leg: 'short', exchange: normalizeExchange(shortExchange) }
  ];

  const targets: PairTradeTarget[] = [];
  const invalidExchanges: string[] = [];
  const failedExchanges: SupportedExchange[] = [];
  const duplicateExchanges: SupportedExchange[] = [];
  const seenExchanges = new Set<SupportedExchange>();

  entries.forEach((entry) => {
    if (!entry.exchange) {
      return;
    }
    if (!isSupportedExchange(entry.exchange)) {
      if (!invalidExchanges.includes(entry.exchange)) {
        invalidExchanges.push(entry.exchange);
      }
      return;
    }
    if (seenExchanges.has(entry.exchange)) {
      if (!duplicateExchanges.includes(entry.exchange)) {
        duplicateExchanges.push(entry.exchange);
      }
      return;
    }
    const url = buildExchangeTradeUrl(entry.exchange, normalizedSymbol);
    if (!url) {
      failedExchanges.push(entry.exchange);
      return;
    }
    seenExchanges.add(entry.exchange);
    targets.push({
      exchange: entry.exchange,
      leg: entry.leg,
      url
    });
  });

  return {
    symbol: normalizedSymbol,
    targets,
    invalidExchanges,
    failedExchanges,
    duplicateExchanges
  };
}

export function buildPairTradeUrls(
  longExchange: string,
  shortExchange: string,
  symbol: string,
): string[] {
  return buildPairTradeTargets(longExchange, shortExchange, symbol).targets.map((item) => item.url);
}
