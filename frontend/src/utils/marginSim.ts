import type {
  MarginSimulation,
  MarginSimulationEvent,
  OpportunityBoardLeg,
  OpportunityBoardRow,
  SettlementEventPreview
} from '../types/market';

const EVENT_MATCH_TOLERANCE_MS = 60_000;
const MAX_FALLBACK_EVENTS = 96;
const MAX_FALLBACK_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;

type LegSide = 'long' | 'short';

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

function parseTimeMs(input: string): number | null {
  if (!input) {
    return null;
  }
  const value = Date.parse(input);
  return Number.isFinite(value) ? value : null;
}

function sideText(side: LegSide | null): string {
  if (side === 'long') {
    return '多腿';
  }
  if (side === 'short') {
    return '空腿';
  }
  return '未知';
}

function normalizeKind(input: SettlementEventPreview['kind'], side: LegSide | null): SettlementEventPreview['kind'] {
  if (input === 'hedged' || input === 'single_side') {
    return input;
  }
  return side ? 'single_side' : 'unknown';
}

function resolveEventAmountRate(event: SettlementEventPreview): number | null {
  if (typeof event.amountRate === 'number' && Number.isFinite(event.amountRate)) {
    return event.amountRate;
  }
  if (typeof event.hedgedRate === 'number' && Number.isFinite(event.hedgedRate)) {
    return event.hedgedRate;
  }
  if (typeof event.singleSideRate === 'number' && Number.isFinite(event.singleSideRate)) {
    return event.singleSideRate;
  }
  if (event.kind === 'hedged' && typeof event.longRateRaw === 'number' && Number.isFinite(event.longRateRaw) && typeof event.shortRateRaw === 'number' && Number.isFinite(event.shortRateRaw)) {
    return event.shortRateRaw - event.longRateRaw;
  }
  if (event.kind === 'single_side' && event.side === 'short' && typeof event.shortRateRaw === 'number' && Number.isFinite(event.shortRateRaw)) {
    return event.shortRateRaw;
  }
  if (event.kind === 'single_side' && event.side === 'long' && typeof event.longRateRaw === 'number' && Number.isFinite(event.longRateRaw)) {
    return -event.longRateRaw;
  }
  return null;
}

function normalizeEvent(event: SettlementEventPreview, index: number): SettlementEventPreview {
  const side = event.side === 'long' || event.side === 'short' ? event.side : null;
  const kind = normalizeKind(event.kind, side);
  const amountRate = resolveEventAmountRate(event);
  const summary = event.summary?.trim() || (kind === 'single_side' ? `${sideText(side)}单边结算` : '同结算');

  return {
    id: event.id?.trim() || `event-${index + 1}`,
    eventTime: event.eventTime?.trim() || '',
    kind,
    side,
    amountRate,
    hedgedRate: event.hedgedRate,
    singleSideRate: event.singleSideRate,
    longRateRaw: event.longRateRaw,
    shortRateRaw: event.shortRateRaw,
    summary
  };
}

function sortEventsByTime(events: SettlementEventPreview[]): SettlementEventPreview[] {
  return [...events].sort((a, b) => {
    const aMs = parseTimeMs(a.eventTime);
    const bMs = parseTimeMs(b.eventTime);
    if (aMs === null && bMs === null) {
      return 0;
    }
    if (aMs === null) {
      return 1;
    }
    if (bMs === null) {
      return -1;
    }
    return aMs - bMs;
  });
}

function fallbackEvent(event: Omit<SettlementEventPreview, 'id'>, index: number): SettlementEventPreview {
  return {
    ...event,
    id: `fallback-${index + 1}`
  };
}

function buildFallbackSettlementEvents(row: OpportunityBoardRow): SettlementEventPreview[] {
  const longIntervalHours = resolveIntervalHours(row.longLeg);
  const shortIntervalHours = resolveIntervalHours(row.shortLeg);
  if (longIntervalHours === null || shortIntervalHours === null) {
    return [];
  }

  const longFundingRateRaw = resolveFundingRateRaw(row.longLeg, longIntervalHours);
  const shortFundingRateRaw = resolveFundingRateRaw(row.shortLeg, shortIntervalHours);
  if (longFundingRateRaw === null || shortFundingRateRaw === null) {
    return [];
  }

  const longIntervalMs = longIntervalHours * 60 * 60 * 1000;
  const shortIntervalMs = shortIntervalHours * 60 * 60 * 1000;
  const longNextMs = parseTimeMs(row.longLeg.nextFundingTime);
  const shortNextMs = parseTimeMs(row.shortLeg.nextFundingTime);

  if (longNextMs === null || shortNextMs === null) {
    const fallbackTime = row.nextSettlementTime || row.longLeg.nextFundingTime || row.shortLeg.nextFundingTime || '';
    if (!fallbackTime) {
      return [];
    }
    return [
      fallbackEvent(
        {
          eventTime: fallbackTime,
          kind: 'hedged',
          side: null,
          amountRate: shortFundingRateRaw - longFundingRateRaw,
          hedgedRate: shortFundingRateRaw - longFundingRateRaw,
          singleSideRate: 0,
          longRateRaw: longFundingRateRaw,
          shortRateRaw: shortFundingRateRaw,
          summary: '同结算'
        },
        0
      )
    ];
  }

  let longCursor = longNextMs;
  let shortCursor = shortNextMs;
  const deadline = Math.min(longNextMs, shortNextMs) + MAX_FALLBACK_WINDOW_MS;
  const events: SettlementEventPreview[] = [];

  for (let index = 0; index < MAX_FALLBACK_EVENTS; index += 1) {
    if (Math.abs(longCursor - shortCursor) <= EVENT_MATCH_TOLERANCE_MS) {
      const eventMs = Math.max(longCursor, shortCursor);
      events.push(
        fallbackEvent(
          {
            eventTime: new Date(eventMs).toISOString(),
            kind: 'hedged',
            side: null,
            amountRate: shortFundingRateRaw - longFundingRateRaw,
            hedgedRate: shortFundingRateRaw - longFundingRateRaw,
            singleSideRate: 0,
            longRateRaw: longFundingRateRaw,
            shortRateRaw: shortFundingRateRaw,
            summary: '同结算'
          },
          index
        )
      );
      break;
    }

    if (longCursor < shortCursor) {
      events.push(
        fallbackEvent(
          {
            eventTime: new Date(longCursor).toISOString(),
            kind: 'single_side',
            side: 'long',
            amountRate: -longFundingRateRaw,
            hedgedRate: 0,
            singleSideRate: -longFundingRateRaw,
            longRateRaw: longFundingRateRaw,
            shortRateRaw: shortFundingRateRaw,
            summary: '多腿单边结算'
          },
          index
        )
      );
      longCursor += longIntervalMs;
    } else {
      events.push(
        fallbackEvent(
          {
            eventTime: new Date(shortCursor).toISOString(),
            kind: 'single_side',
            side: 'short',
            amountRate: shortFundingRateRaw,
            hedgedRate: 0,
            singleSideRate: shortFundingRateRaw,
            longRateRaw: longFundingRateRaw,
            shortRateRaw: shortFundingRateRaw,
            summary: '空腿单边结算'
          },
          index
        )
      );
      shortCursor += shortIntervalMs;
    }

    if (Math.min(longCursor, shortCursor) > deadline) {
      break;
    }
  }

  if (events.length === 0) {
    events.push(
      fallbackEvent(
        {
          eventTime: new Date(Math.max(longNextMs, shortNextMs)).toISOString(),
          kind: 'hedged',
          side: null,
          amountRate: shortFundingRateRaw - longFundingRateRaw,
          hedgedRate: shortFundingRateRaw - longFundingRateRaw,
          singleSideRate: 0,
          longRateRaw: longFundingRateRaw,
          shortRateRaw: shortFundingRateRaw,
          summary: '同结算'
        },
        0
      )
    );
  }

  return sortEventsByTime(events);
}

function rateParts(events: SettlementEventPreview[]): { hedgedRate: number; singleSideRate: number; totalRate: number } {
  let hedgedRate = 0;
  let singleSideRate = 0;
  events.forEach((event) => {
    const rate = resolveEventAmountRate(event);
    if (rate === null) {
      return;
    }
    if (event.kind === 'single_side') {
      singleSideRate += rate;
      return;
    }
    hedgedRate += rate;
  });
  return {
    hedgedRate,
    singleSideRate,
    totalRate: hedgedRate + singleSideRate
  };
}

function deriveShorterSideFromEvents(events: SettlementEventPreview[]): LegSide | null {
  let longCount = 0;
  let shortCount = 0;
  events.forEach((event) => {
    if (event.kind !== 'single_side') {
      return;
    }
    if (event.side === 'long') {
      longCount += 1;
    } else if (event.side === 'short') {
      shortCount += 1;
    }
  });
  if (longCount === shortCount) {
    return null;
  }
  return longCount > shortCount ? 'long' : 'short';
}

export function parseMarginUsd(input: string): number | null {
  const parsed = Number(input.replace(/,/g, '').trim());
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

export function resolveSettlementEvents(row: OpportunityBoardRow): SettlementEventPreview[] {
  const source = Array.isArray(row.settlementEventsPreview) ? row.settlementEventsPreview : [];
  if (source.length > 0) {
    return sortEventsByTime(source.map((event, index) => normalizeEvent(event, index)));
  }
  return buildFallbackSettlementEvents(row);
}

export function resolveSingleSideEventCount(row: OpportunityBoardRow, events?: SettlementEventPreview[]): number {
  const resolvedEvents = events ?? resolveSettlementEvents(row);
  const derivedCount = resolvedEvents.filter((event) => event.kind === 'single_side').length;
  if (typeof row.singleSideEventCount === 'number' && Number.isFinite(row.singleSideEventCount) && row.singleSideEventCount >= 0) {
    const normalized = Math.round(row.singleSideEventCount);
    return normalized === 0 ? derivedCount : normalized;
  }
  return derivedCount;
}

export function resolveNextSettlementTime(row: OpportunityBoardRow, events?: SettlementEventPreview[]): string {
  if (row.nextSettlementTime) {
    return row.nextSettlementTime;
  }
  const resolvedEvents = events ?? resolveSettlementEvents(row);
  const hedgedTime = [...resolvedEvents].reverse().find((event) => event.kind === 'hedged' && event.eventTime)?.eventTime;
  if (hedgedTime) {
    return hedgedTime;
  }
  return resolvedEvents[resolvedEvents.length - 1]?.eventTime ?? '';
}

export function calcMarginSimulation(row: OpportunityBoardRow, marginUsd: number): MarginSimulation | null {
  if (!Number.isFinite(marginUsd) || marginUsd <= 0) {
    return null;
  }

  const leverage = typeof row.maxUsableLeverage === 'number' && Number.isFinite(row.maxUsableLeverage) && row.maxUsableLeverage > 0 ? row.maxUsableLeverage : 1;
  const notionalUsd = marginUsd * leverage;
  const events = resolveSettlementEvents(row);
  if (events.length === 0) {
    return null;
  }

  const simulationEvents: MarginSimulationEvent[] = [];
  events.forEach((event, index) => {
    const amountRate = resolveEventAmountRate(event);
    if (amountRate === null) {
      return;
    }
    simulationEvents.push({
      id: event.id || `event-${index + 1}`,
      eventTime: event.eventTime,
      kind: event.kind,
      side: event.side,
      amountRate,
      pnlUsd: notionalUsd * amountRate,
      summary: event.summary
    });
  });

  if (simulationEvents.length === 0) {
    return null;
  }

  const { hedgedRate, singleSideRate, totalRate } = rateParts(events);
  const singleSideEventCount = resolveSingleSideEventCount(row, events);
  const nextSettlementTime = resolveNextSettlementTime(row, events);
  const intervalMismatch = row.intervalMismatch || singleSideEventCount > 0;
  const shorterIntervalSide = row.shorterIntervalSide ?? deriveShorterSideFromEvents(events);

  const eventMsList = simulationEvents.map((event) => parseTimeMs(event.eventTime)).filter((value): value is number => value !== null);
  const windowStartTime = eventMsList.length > 0 ? new Date(Math.min(...eventMsList)).toISOString() : '';
  const windowEndTime = eventMsList.length > 0 ? new Date(Math.max(...eventMsList)).toISOString() : '';

  return {
    marginUsd,
    leverage,
    notionalUsd,
    eventCount: simulationEvents.length,
    singleSideEventCount,
    hedgedRate,
    singleSideRate,
    totalRate,
    expectedPnlUsd: notionalUsd * totalRate,
    intervalMismatch,
    shorterIntervalSide,
    nextSettlementTime,
    windowStartTime,
    windowEndTime,
    events: simulationEvents
  };
}
