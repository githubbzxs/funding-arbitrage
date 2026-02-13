import { describe, expect, it } from 'vitest';
import type { OpportunityBoardRow, SettlementEventPreview } from '../types/market';
import { calcMarginSimulation, resolveNextSettlementTime, resolveSettlementEvents, resolveSingleSideEventCount } from './marginSim';

function createRow(overrides?: Partial<OpportunityBoardRow>): OpportunityBoardRow {
  return {
    id: 'BTCUSDT-binance-okx',
    symbol: 'BTCUSDT',
    longExchange: 'binance',
    shortExchange: 'okx',
    longLeg: {
      exchange: 'binance',
      openInterestUsd: null,
      volume24hUsd: null,
      fundingRateRaw: -0.0001,
      fundingRate1h: null,
      fundingRate8h: null,
      fundingRate1y: null,
      nextFundingTime: '2026-01-01T08:00:00Z',
      settlementInterval: '8h',
      settlementIntervalHours: 8,
      maxLeverage: 20,
      leveragedNominalRate1y: null
    },
    shortLeg: {
      exchange: 'okx',
      openInterestUsd: null,
      volume24hUsd: null,
      fundingRateRaw: 0.0002,
      fundingRate1h: null,
      fundingRate8h: null,
      fundingRate1y: null,
      nextFundingTime: '2026-01-01T08:00:00Z',
      settlementInterval: '8h',
      settlementIntervalHours: 8,
      maxLeverage: 20,
      leveragedNominalRate1y: null
    },
    intervalMismatch: false,
    shorterIntervalSide: null,
    spreadRate1h: null,
    spreadRate8h: null,
    spreadRate1yNominal: 0,
    leveragedSpreadRate1yNominal: 0,
    nextCycleScore: 0,
    nextCycleScoreUnleveraged: 0,
    nextSettlementTime: '',
    settlementEventsPreview: [],
    singleSideEventCount: 0,
    maxUsableLeverage: 10,
    ...overrides
  };
}

describe('marginSim', () => {
  it('同间隔时应生成同结算事件并按窗口计算收益', () => {
    const row = createRow();
    const events = resolveSettlementEvents(row);
    const simulation = calcMarginSimulation(row, 100);

    expect(events).toHaveLength(1);
    expect(events[0]?.kind).toBe('hedged');
    expect(resolveSingleSideEventCount(row, events)).toBe(0);
    expect(resolveNextSettlementTime(row, events)).toBe(events[0]?.eventTime);

    expect(simulation).not.toBeNull();
    expect(simulation?.eventCount).toBe(1);
    expect(simulation?.singleSideEventCount).toBe(0);
    expect(simulation?.totalRate).toBeCloseTo(0.0003, 10);
    expect(simulation?.expectedPnlUsd).toBeCloseTo(0.3, 10);
  });

  it('不同间隔时应包含单边事件并输出逐次金额', () => {
    const row = createRow({
      intervalMismatch: true,
      shorterIntervalSide: 'short',
      longLeg: {
        ...createRow().longLeg,
        nextFundingTime: '2026-01-01T08:00:00Z',
        settlementInterval: '8h',
        settlementIntervalHours: 8
      },
      shortLeg: {
        ...createRow().shortLeg,
        nextFundingTime: '2026-01-01T04:00:00Z',
        settlementInterval: '4h',
        settlementIntervalHours: 4
      }
    });

    const events = resolveSettlementEvents(row);
    const simulation = calcMarginSimulation(row, 100);

    expect(events.length).toBeGreaterThanOrEqual(2);
    expect(resolveSingleSideEventCount(row, events)).toBe(1);
    expect(events[0]?.kind).toBe('single_side');
    expect(events[0]?.side).toBe('short');

    expect(simulation).not.toBeNull();
    expect(simulation?.singleSideEventCount).toBe(1);
    expect(simulation?.events.length).toBe(2);
    expect(simulation?.events[0]?.pnlUsd).toBeCloseTo(0.2, 10);
    expect(simulation?.events[1]?.pnlUsd).toBeCloseTo(0.3, 10);
    expect(simulation?.expectedPnlUsd).toBeCloseTo(0.5, 10);
  });

  it('后端提供 settlementEventsPreview 时应优先使用该事件列表', () => {
    const previewEvents: SettlementEventPreview[] = [
      {
        id: 'custom-1',
        eventTime: '2026-01-01T06:00:00Z',
        kind: 'single_side',
        side: 'short',
        amountRate: 0.001,
        hedgedRate: 0,
        singleSideRate: 0.001,
        longRateRaw: -0.0001,
        shortRateRaw: 0.0002,
        summary: '空腿单边结算'
      },
      {
        id: 'custom-2',
        eventTime: '2026-01-01T08:00:00Z',
        kind: 'hedged',
        side: null,
        amountRate: -0.0002,
        hedgedRate: -0.0002,
        singleSideRate: 0,
        longRateRaw: -0.0001,
        shortRateRaw: 0.0002,
        summary: '同结算'
      }
    ];
    const row = createRow({
      settlementEventsPreview: previewEvents,
      singleSideEventCount: 1
    });

    const events = resolveSettlementEvents(row);
    const simulation = calcMarginSimulation(row, 100);

    expect(events).toHaveLength(2);
    expect(events[0]?.id).toBe('custom-1');
    expect(events[1]?.id).toBe('custom-2');
    expect(simulation).not.toBeNull();
    expect(simulation?.singleSideEventCount).toBe(1);
    expect(simulation?.expectedPnlUsd).toBeCloseTo(0.8, 10);
  });
});
