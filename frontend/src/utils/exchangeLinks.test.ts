import { describe, expect, it } from 'vitest';
import * as exchangeLinksModule from './exchangeLinks';

type PairTradeTarget = {
  exchange: string;
  url: string;
};

type PairTradeTargetsResult = {
  targets: PairTradeTarget[];
  invalidExchanges: string[];
  failedExchanges: string[];
  duplicateExchanges: string[];
};

type BuildPairTradeTargetsFn = (longExchange: string, shortExchange: string, symbol: string) => unknown;

function getBuildPairTradeTargets(): BuildPairTradeTargetsFn {
  const candidate = (exchangeLinksModule as Record<string, unknown>).buildPairTradeTargets;
  if (typeof candidate !== 'function') {
    throw new Error('exchangeLinks.ts 需要导出 buildPairTradeTargets 函数。');
  }
  return candidate as BuildPairTradeTargetsFn;
}

function readStringList(value: unknown, fieldName: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
    throw new Error(`字段 ${fieldName} 必须是字符串数组。`);
  }
  return value;
}

function normalizeResult(raw: unknown): PairTradeTargetsResult {
  if (!raw || typeof raw !== 'object') {
    throw new Error('buildPairTradeTargets 返回值必须是对象。');
  }
  const data = raw as Record<string, unknown>;
  if (!Array.isArray(data.targets)) {
    throw new Error('字段 targets 必须是数组。');
  }

  const targets = data.targets.map((item, index) => {
    if (!item || typeof item !== 'object') {
      throw new Error(`targets[${index}] 必须是对象。`);
    }
    const target = item as Record<string, unknown>;
    if (typeof target.exchange !== 'string' || target.exchange.trim().length === 0) {
      throw new Error(`targets[${index}].exchange 必须是非空字符串。`);
    }
    if (typeof target.url !== 'string' || !/^https?:\/\//.test(target.url)) {
      throw new Error(`targets[${index}].url 必须是有效 http(s) 链接。`);
    }
    return {
      exchange: target.exchange.toLowerCase(),
      url: target.url
    };
  });

  const duplicateExchanges = Array.isArray(data.duplicateExchanges)
    ? readStringList(data.duplicateExchanges, 'duplicateExchanges').map((item) => item.toLowerCase())
    : [];

  return {
    targets,
    invalidExchanges: readStringList(data.invalidExchanges, 'invalidExchanges').map((item) => item.toLowerCase()),
    failedExchanges: readStringList(data.failedExchanges, 'failedExchanges').map((item) => item.toLowerCase()),
    duplicateExchanges
  };
}

describe('buildPairTradeTargets', () => {
  it('有效 long/short + symbol 应返回两个目标链接', () => {
    const buildPairTradeTargets = getBuildPairTradeTargets();
    const result = normalizeResult(buildPairTradeTargets('binance', 'okx', 'BTCUSDT'));

    expect(result.targets).toHaveLength(2);
    expect(result.targets.map((item) => item.exchange)).toEqual(['binance', 'okx']);
    expect(result.invalidExchanges).toEqual([]);
    expect(result.failedExchanges).toEqual([]);
    expect(result.duplicateExchanges).toEqual([]);
  });

  it('非法交易所应返回可诊断失败信息', () => {
    const buildPairTradeTargets = getBuildPairTradeTargets();
    const result = normalizeResult(buildPairTradeTargets('unknown-exchange', 'okx', 'BTCUSDT'));

    expect(result.targets).toHaveLength(1);
    expect(result.targets[0]?.exchange).toBe('okx');
    expect(result.invalidExchanges).toContain('unknown-exchange');
  });
});
