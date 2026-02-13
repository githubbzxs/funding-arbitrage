import { describe, expect, it, vi } from 'vitest';
import type { PairTradeTarget } from './exchangeLinks';
import { openPairTargetsInNewTabs, type OpenWindowFn, type PopupWindowLike } from './popupOpen';

function createPopup(): { popup: PopupWindowLike; replace: ReturnType<typeof vi.fn> } {
  const replace = vi.fn();
  const popup: PopupWindowLike = {
    opener: {},
    location: { replace },
    close: vi.fn()
  };
  return { popup, replace };
}

describe('openPairTargetsInNewTabs', () => {
  it('两次都成功时 opened 应为 2', () => {
    const popupA = createPopup();
    const popupB = createPopup();
    const openWindow = vi.fn<OpenWindowFn>().mockImplementationOnce(() => popupA.popup).mockImplementationOnce(() => popupB.popup);
    const targets: PairTradeTarget[] = [
      { exchange: 'binance', leg: 'long', url: 'https://www.binance.com/en/futures/BTCUSDT' },
      { exchange: 'okx', leg: 'short', url: 'https://www.okx.com/trade-swap/BTC-usdt-swap' }
    ];

    const result = openPairTargetsInNewTabs(targets, { openWindow });

    expect(result.requested).toBe(2);
    expect(result.opened).toBe(2);
    expect(result.blockedExchanges).toEqual([]);
    expect(result.openedExchanges).toEqual(['binance', 'okx']);
    expect(openWindow).toHaveBeenCalledTimes(2);
    expect(openWindow.mock.calls[0]?.[0]).toBe('about:blank');
    expect(openWindow.mock.calls[1]?.[0]).toBe('about:blank');
    expect(popupA.replace).toHaveBeenCalledWith(targets[0].url);
    expect(popupB.replace).toHaveBeenCalledWith(targets[1].url);
  });

  it('一次失败时 opened 应为 1 且 blockedExchanges 正确', () => {
    const popupA = createPopup();
    const openWindow = vi.fn<OpenWindowFn>().mockImplementationOnce(() => popupA.popup).mockImplementationOnce(() => null);
    const targets: PairTradeTarget[] = [
      { exchange: 'binance', leg: 'long', url: 'https://www.binance.com/en/futures/BTCUSDT' },
      { exchange: 'okx', leg: 'short', url: 'https://www.okx.com/trade-swap/BTC-usdt-swap' }
    ];

    const result = openPairTargetsInNewTabs(targets, { openWindow });

    expect(result.requested).toBe(2);
    expect(result.opened).toBe(1);
    expect(result.blockedExchanges).toEqual(['okx']);
    expect(result.openedExchanges).toEqual(['binance']);
    expect(openWindow).toHaveBeenCalledTimes(2);
    expect(popupA.replace).toHaveBeenCalledWith(targets[0].url);
  });
});
