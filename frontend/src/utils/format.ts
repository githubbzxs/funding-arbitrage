const compactFormatter = new Intl.NumberFormat('zh-CN', {
  notation: 'compact',
  maximumFractionDigits: 2
});

function asPercentValue(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return value * 100;
}

export function formatMoney(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-';
  }
  if (Math.abs(value) < 1000) {
    return `$${value.toFixed(2)}`;
  }
  return `$${compactFormatter.format(value)}`;
}

export function formatPercent(value: number | null | undefined, digits = 3): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-';
  }
  const parsed = asPercentValue(value);
  return `${parsed.toFixed(digits)}%`;
}

export function formatLeverage(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    return '-';
  }
  return `${value.toFixed(0)}x`;
}

export function formatTime(value: string): string {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '-';
  }
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

export function toNumber(input: unknown, fallback = 0): number {
  if (typeof input === 'number') {
    return Number.isFinite(input) ? input : fallback;
  }
  if (typeof input === 'string') {
    const parsed = Number(input.replace(/,/g, '').trim());
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
}
