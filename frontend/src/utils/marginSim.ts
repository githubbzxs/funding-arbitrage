import type { MarginSimulation, OpportunityBoardLeg, OpportunityBoardRow } from '../types/market';

const DEFAULT_HORIZON_HOURS = 24;

function parseIntervalText(text: string): number | null {
  if (!text) {
    return null;
  }
  const match = text.trim().toLowerCase().match(/^(\d+(?:\.\d+)?)h$/);
  if (!match) {
    return null;
  }
  const parsed = Number(match[1]);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function resolveIntervalHours(leg: OpportunityBoardLeg): number | null {
  if (typeof leg.settlementIntervalHours === 'number' && Number.isFinite(leg.settlementIntervalHours) && leg.settlementIntervalHours > 0) {
    return leg.settlementIntervalHours;
  }
  return parseIntervalText(leg.settlementInterval);
}

function resolveFundingRateRaw(leg: OpportunityBoardLeg, intervalHours: number): number | null {
  if (typeof leg.fundingRateRaw === 'number' && Number.isFinite(leg.fundingRateRaw)) {
    return leg.fundingRateRaw;
  }
  if (typeof leg.fundingRate1h === 'number' && Number.isFinite(leg.fundingRate1h)) {
    return leg.fundingRate1h * intervalHours;
  }
  return null;
}

export function parseMarginUsd(input: string): number | null {
  const parsed = Number(input.replace(/,/g, '').trim());
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

export function calcMarginSimulation(row: OpportunityBoardRow, marginUsd: number, horizonHours = DEFAULT_HORIZON_HOURS): MarginSimulation | null {
  if (!Number.isFinite(marginUsd) || marginUsd <= 0) {
    return null;
  }
  if (!Number.isFinite(horizonHours) || horizonHours <= 0) {
    return null;
  }

  const longIntervalHours = resolveIntervalHours(row.longLeg);
  const shortIntervalHours = resolveIntervalHours(row.shortLeg);
  if (longIntervalHours === null || shortIntervalHours === null) {
    return null;
  }

  const longFundingRateRaw = resolveFundingRateRaw(row.longLeg, longIntervalHours);
  const shortFundingRateRaw = resolveFundingRateRaw(row.shortLeg, shortIntervalHours);
  if (longFundingRateRaw === null || shortFundingRateRaw === null) {
    return null;
  }

  const leverage = typeof row.maxUsableLeverage === 'number' && Number.isFinite(row.maxUsableLeverage) && row.maxUsableLeverage > 0 ? row.maxUsableLeverage : 1;
  const notionalUsd = marginUsd * leverage;
  const longEvents = horizonHours / longIntervalHours;
  const shortEvents = horizonHours / shortIntervalHours;
  const intervalMismatch = Math.abs(longIntervalHours - shortIntervalHours) > 1e-9;

  let hedgedRate = 0;
  let singleSideRate = 0;
  let shorterIntervalSide: 'long' | 'short' | null = null;
  if (!intervalMismatch) {
    hedgedRate = (shortFundingRateRaw - longFundingRateRaw) * longEvents;
  } else {
    const hedgedEvents = Math.min(longEvents, shortEvents);
    hedgedRate = (shortFundingRateRaw - longFundingRateRaw) * hedgedEvents;
    if (shortEvents > longEvents) {
      shorterIntervalSide = 'short';
      singleSideRate = (shortEvents - longEvents) * shortFundingRateRaw;
    } else {
      shorterIntervalSide = 'long';
      singleSideRate = (longEvents - shortEvents) * -longFundingRateRaw;
    }
  }

  const totalRate = hedgedRate + singleSideRate;
  return {
    marginUsd,
    leverage,
    notionalUsd,
    horizonHours,
    longIntervalHours,
    shortIntervalHours,
    longEvents,
    shortEvents,
    hedgedRate,
    singleSideRate,
    totalRate,
    expectedPnlUsd: notionalUsd * totalRate,
    intervalMismatch,
    shorterIntervalSide,
  };
}
