const SUPPORTED_EXCHANGES = ['binance', 'okx', 'bybit', 'bitget', 'gateio'] as const;

type SupportedExchange = (typeof SUPPORTED_EXCHANGES)[number];

function normalizeSymbol(symbol: string): string {
  return symbol.toUpperCase().replace(/[^A-Z0-9]/g, '');
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
  const normalizedExchange = exchange.toLowerCase();
  if (!isSupportedExchange(normalizedExchange)) {
    return null;
  }

  const normalizedSymbol = normalizeSymbol(symbol);
  const baseAsset = resolveBaseAsset(normalizedSymbol);

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

export function buildPairTradeUrls(
  longExchange: string,
  shortExchange: string,
  symbol: string,
): string[] {
  const urls = [buildExchangeTradeUrl(longExchange, symbol), buildExchangeTradeUrl(shortExchange, symbol)];
  const normalized = urls.filter((item): item is string => Boolean(item));
  return normalized.filter((item, index, list) => list.indexOf(item) === index);
}
