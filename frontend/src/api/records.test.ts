import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchOrders, fetchPositions, fetchRiskEvents } from './records';

describe('records api', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetchPositions/fetchOrders 支持 items 格式', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(async () => ({
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => ({
          items: [
            {
              id: 'p1',
              symbol: 'BTCUSDT',
              long_exchange: 'okx',
              short_exchange: 'binance',
              long_qty: 1,
              short_qty: 1,
              mode: 'manual',
              status: 'open',
              opened_at: '2026-02-15T00:00:00Z',
              created_at: '2026-02-15T00:00:00Z',
              updated_at: '2026-02-15T00:00:00Z',
            },
          ],
        }),
        text: async () => '',
      }))
      .mockImplementationOnce(async () => ({
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => ({
          items: [
            {
              id: 'o1',
              action: 'open',
              mode: 'manual',
              status: 'ok',
              exchange: 'okx',
              symbol: 'BTCUSDT',
              side: 'buy',
              quantity: 1,
              created_at: '2026-02-15T00:00:00Z',
              updated_at: '2026-02-15T00:00:00Z',
            },
          ],
        }),
        text: async () => '',
      }));

    vi.stubGlobal('fetch', fetchMock);

    const positions = await fetchPositions();
    const orders = await fetchOrders();
    expect(positions[0].id).toBe('p1');
    expect(orders[0].id).toBe('o1');
  });

  it('fetchRiskEvents 能解析 resolved 字段', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => ({
          items: [
            {
              id: 'r1',
              event_type: 'open_second_leg_failed',
              severity: 'critical',
              message: '测试',
              context: {},
              resolved: false,
              created_at: '2026-02-15T00:00:00Z',
              updated_at: '2026-02-15T00:00:00Z',
            },
          ],
        }),
        text: async () => '',
      }))
    );

    const events = await fetchRiskEvents({ resolved: false });
    expect(events).toHaveLength(1);
    expect(events[0].resolved).toBe(false);
    expect(events[0].severity).toBe('critical');
  });
});
