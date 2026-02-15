import { afterEach, describe, expect, it, vi } from 'vitest';
import { createTemplate, fetchTemplates, updateTemplate } from './templates';

describe('templates api', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetchTemplates 能解析 items 列表', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => ({
          items: [
            {
              id: 't1',
              name: '模板1',
              symbol: 'BTCUSDT',
              long_exchange: 'okx',
              short_exchange: 'binance',
              quantity: 0.01,
              notional_usd: 1000,
              leverage: 5,
              hold_hours: 8,
              note: null,
              created_at: '2026-02-15T00:00:00Z',
              updated_at: '2026-02-15T00:00:00Z',
            },
          ],
        }),
        text: async () => '',
      }))
    );

    const list = await fetchTemplates();
    expect(list).toHaveLength(1);
    expect(list[0].id).toBe('t1');
    expect(list[0].long_exchange).toBe('okx');
    expect(list[0].quantity).toBe(0.01);
  });

  it('create/update 模板返回单对象时能正确解析', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 't2',
          name: '模板2',
          symbol: 'ETHUSDT',
          long_exchange: 'bybit',
          short_exchange: 'okx',
          quantity: 0.02,
          notional_usd: 2000,
          leverage: 3,
          hold_hours: 4,
          note: 'test',
          created_at: '2026-02-15T00:00:00Z',
          updated_at: '2026-02-15T00:00:00Z',
        }),
        text: async () => '',
      }))
    );

    const created = await createTemplate({
      name: '模板2',
      symbol: 'ETHUSDT',
      long_exchange: 'bybit',
      short_exchange: 'okx',
    });
    expect(created.id).toBe('t2');
    expect(created.quantity).toBe(0.02);

    const updated = await updateTemplate('t2', { name: '模板2-更新' });
    expect(updated.symbol).toBe('ETHUSDT');
    expect(updated.quantity).toBe(0.02);
  });
});
